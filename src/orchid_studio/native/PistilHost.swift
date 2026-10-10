import AppKit
import AVFoundation
import AudioToolbox
import CoreAudioKit
import CoreAudio

// This process loads the user's installed AU. It never opens a hardware MIDI port.
let app = NSApplication.shared
app.setActivationPolicy(.regular)
let protocolOutput = FileHandle(fileDescriptor: dup(STDOUT_FILENO), closeOnDealloc: true)
// Third-party plugin diagnostics must not corrupt the JSON response stream.
dup2(STDERR_FILENO, STDOUT_FILENO)
func reply(_ value: [String:Any]) {
    if let data = try? JSONSerialization.data(withJSONObject:value,options:[.sortedKeys]) {
        protocolOutput.write(data); protocolOutput.write(Data([10]))
    }
}
func fourCC(_ text:String)->UInt32 { text.utf8.reduce(0) { ($0 << 8) | UInt32($1) } }
struct HostError: Error { let message:String }
let engine = AVAudioEngine()
var units:[AVAudioUnitMIDIInstrument] = []
var drumSampler:DrumSampler!
let drumMixer=AVAudioMixerNode()
let audioActivity=ProcessInfo.processInfo.beginActivity(options:[.userInitiated,.latencyCritical],reason:"Orchid Studio live audio")
var windows:[Int:NSWindow] = [:]
var gains:[AVAudioMixerNode] = []
// Each voice: Pistil -> delay -> reverb -> its gain. Both effects start bypassed: the sound is unchanged until set.
var delays:[AVAudioUnitDelay] = []
var reverbs:[AVAudioUnitReverb] = []
let rooms:[String:AVAudioUnitReverbPreset] = ["small":.smallRoom,"medium":.mediumRoom,"large":.largeRoom,
    "chamber":.mediumChamber,"hall":.mediumHall,"large-hall":.largeHall,"plate":.plate,"cathedral":.cathedral]
var ready = false
var outputEnabled = false
var bpm:Double = 124
var stateReadyAt=Date.distantPast
var audioError:String?
var routeRevision=0
var peaks = Array(repeating:Float(0),count:6)
let peakLock = NSLock()

func audioInfo()->[String:Any] {
    var device=AudioDeviceID(0)
    var size=UInt32(MemoryLayout<AudioDeviceID>.size)
    if let unit=engine.outputNode.audioUnit {
        AudioUnitGetProperty(unit,kAudioOutputUnitProperty_CurrentDevice,kAudioUnitScope_Global,0,&device,&size)
    }
    var name:CFString="Unknown output" as CFString
    var address=AudioObjectPropertyAddress(mSelector:kAudioObjectPropertyName,mScope:kAudioObjectPropertyScopeGlobal,mElement:kAudioObjectPropertyElementMain)
    size=UInt32(MemoryLayout<CFString>.size)
    AudioObjectGetPropertyData(device,&address,0,nil,&size,&name)
    return ["running":engine.isRunning,"device":name as String,"device_id":device,
            "sample_rate":engine.outputNode.inputFormat(forBus:0).sampleRate,
            "error":audioError as Any? ?? NSNull(),"route_changes":routeRevision]
}
let routeObserver=NotificationCenter.default.addObserver(forName:.AVAudioEngineConfigurationChange,object:engine,queue:.main) { _ in
    guard ready else {return}
    routeRevision += 1
    let revision=routeRevision
    DispatchQueue.main.asyncAfter(deadline:.now()+0.15) {
        guard revision==routeRevision,ready else {return}
        do {
            if !engine.isRunning {
                for slot in 0..<units.count {panic(slot)}
                let format=engine.outputNode.inputFormat(forBus:0)
                guard format.sampleRate>0,format.channelCount>0 else {throw HostError(message:"No audio output is available")}
                engine.disconnectNodeOutput(engine.mainMixerNode)
                engine.connect(engine.mainMixerNode,to:engine.outputNode,format:format)
                try engine.start()
            }
            audioError=nil
            reply(["event":"audio_route_changed","audio":audioInfo()])
        } catch {
            audioError=String(describing:error)
            reply(["event":"audio_route_error","audio":audioInfo()])
        }
    }
}

func panic(_ slot:Int) {
    for ch in 0..<16 {
        for cc in [64,66,123,120] { units[slot].sendController(UInt8(cc),withValue:0,onChannel:UInt8(ch)) }
    }
}
func stateData(_ slot:Int)throws->Data {
    guard let state=units[slot].auAudioUnit.fullState else {throw HostError(message:"Pistil did not supply state")}
    return try PropertyListSerialization.data(fromPropertyList:state,format:.binary,options:0)
}
func stateInfo(_ slot:Int)->[String:Any] {
    let au=units[slot].auAudioUnit
    peakLock.lock();let peak=peaks[slot];peakLock.unlock()
    return ["slot":slot+1,"preset":au.currentPreset?.name ?? "Pistil",
            "peak":peak,"volume":gains[slot].outputVolume,"pan":gains[slot].pan,
            "editor_open":windows[slot]?.isVisible ?? false]
}
func showEditor(_ slot:Int, id:Any) {
    if let window=windows[slot] {window.makeKeyAndOrderFront(nil);app.activate(ignoringOtherApps:true);reply(["id":id,"status":"ok"]);return}
    units[slot].auAudioUnit.requestViewController { controller in
        DispatchQueue.main.async {
            guard let controller=controller else {reply(["id":id,"status":"error","error":"Pistil did not provide an AU editor"]);return}
            let originalSize=controller.view.frame.size
            let window=NSWindow(contentViewController:controller)
            window.title=slot==5 ? "Orchid Studio · Pistil · Play Along" : slot==4 ? "Orchid Studio · Pistil · Live" : "Orchid Studio · Pistil · Layer \(slot+1)"
            window.styleMask=[.titled,.closable,.miniaturizable,.resizable]
            window.isReleasedWhenClosed=false
            if originalSize.width>200 && originalSize.height>200 {window.setContentSize(originalSize)}
            window.center();window.makeKeyAndOrderFront(nil)
            windows[slot]=window;app.activate(ignoringOtherApps:true)
            reply(["id":id,"status":"ok"])
        }
    }
}
func handle(_ request:[String:Any]) {
    let id=request["id"] ?? NSNull()
    do {
        guard ready else {throw HostError(message:"Pistil is still loading")}
        let command=request["command"] as? String ?? ""
        let slot=(request["slot"] as? Int ?? 1)-1
        guard (0..<6).contains(slot) else {throw HostError(message:"slot must be 1–6")}
        switch command {
        case "status":reply(["id":id,"status":"ok","ready":ready,"output_enabled":outputEnabled,"bpm":bpm,"uptime":ProcessInfo.processInfo.systemUptime,"audio":audioInfo(),"drums":drumSampler.status(),"layers":(0..<6).map{stateInfo($0)}]);return
        case "enable":
            outputEnabled=request["enabled"] as? Bool ?? false
            engine.mainMixerNode.outputVolume=outputEnabled ? 0.35 : 0
        case "tempo":
            guard let value=request["bpm"] as? Double, value.isFinite, (30...300).contains(value) else {throw HostError(message:"invalid BPM")}
            bpm=value
        case "midi":
            guard let bytes=request["message"] as? [Int], bytes.count==3,
                  (0x80..<0xF0).contains(bytes[0]), (0...127).contains(bytes[1]),(0...127).contains(bytes[2]) else {throw HostError(message:"invalid MIDI event")}
            if let at=request["at"] as? Double, let last=units[slot].lastRenderTime,
               last.isHostTimeValid,last.isSampleTimeValid,let schedule=units[slot].auAudioUnit.scheduleMIDIEventBlock {
                let delta=at-AVAudioTime.seconds(forHostTime:last.hostTime)
                let target=last.sampleTime+Int64(max(0,delta)*last.sampleRate)
                let midi=bytes.map{UInt8($0)}
                midi.withUnsafeBufferPointer {buffer in schedule(target,0,3,buffer.baseAddress!)}
            } else {
                units[slot].sendMIDIEvent(UInt8(bytes[0]),data1:UInt8(bytes[1]),data2:UInt8(bytes[2]))
            }
        case "mix":
            guard let volume=request["volume"] as? Double,volume.isFinite,(0...1.5).contains(volume),
                  let pan=request["pan"] as? Double,pan.isFinite,(-1...1).contains(pan) else {throw HostError(message:"invalid mixer values")}
            if request["target"] as? String == "drums" {drumMixer.pan=Float(pan)}
            else {gains[slot].outputVolume=Float(volume);gains[slot].pan=Float(pan)}
        case "fx":
            if let values=request["delay"] as? [String:Any] {
                guard let mix=values["mix"] as? Double,mix.isFinite,(0...100).contains(mix),
                      let time=values["time"] as? Double,time.isFinite,(0.01...2).contains(time),
                      let feedback=values["feedback"] as? Double,feedback.isFinite,(0...95).contains(feedback) else {throw HostError(message:"invalid delay")}
                delays[slot].delayTime=time;delays[slot].feedback=Float(feedback)
                delays[slot].wetDryMix=Float(mix);delays[slot].bypass = mix==0
            }
            if let values=request["reverb"] as? [String:Any] {
                guard let mix=values["mix"] as? Double,mix.isFinite,(0...100).contains(mix),
                      let room=values["room"] as? String,let preset=rooms[room] else {throw HostError(message:"invalid reverb")}
                reverbs[slot].loadFactoryPreset(preset);reverbs[slot].wetDryMix=Float(mix);reverbs[slot].bypass = mix==0
            }
        case "drum-load":
            guard let specs=request["sounds"] as? [[String:Any]] else {throw HostError(message:"sounds array required")}
            try drumSampler.load(specs)
        case "drum-hit":
            guard let sound=request["sound"] as? String else {throw HostError(message:"sound required")}
            try drumSampler.hit(sound,at:request["at"] as? Double ?? ProcessInfo.processInfo.systemUptime,gain:Float(request["velocity"] as? Double ?? 0.5))
        case "drum-volume":
            guard let value=request["volume"] as? Double,value.isFinite,(0...1.5).contains(value) else {throw HostError(message:"invalid drum volume")}
            drumSampler.setVolume(Float(value))
        case "drum-stop":drumSampler.stop()
        case "sound":
            stateReadyAt=Date().addingTimeInterval(0.06)
            guard let bytes=request["message"] as? [Int] else {throw HostError(message:"invalid Sound report")}
            if bytes.count==3 && bytes[0]==0xB0 && bytes[1]==102 && (0..<100).contains(bytes[2]) {
                units[slot].sendMIDIEvent(0xB0,data1:102,data2:UInt8(bytes[2]))
            } else if bytes.count==142 && Array(bytes.prefix(5))==[0xF0,0,0x22,0x0C,0x34] && bytes.last==0xF7 && bytes[5]<100 && bytes.dropFirst(5).dropLast().allSatisfy({(0..<128).contains($0)}) {
                units[slot].sendMIDISysExEvent(Data(bytes.map{UInt8($0)}))
            } else {throw HostError(message:"unsupported Sound report")}
        case "panic":
            drumSampler.stop()
            engine.mainMixerNode.outputVolume=0
            for i in 0..<6 {panic(i)}
            // Drain the 40 ms scheduled MIDI horizon while silent before acknowledging Stop.
            DispatchQueue.main.asyncAfter(deadline:.now()+0.06) {
                for i in 0..<6 {panic(i)}
                engine.mainMixerNode.outputVolume=outputEnabled ? 0.35 : 0
                reply(["id":id,"status":"ok"])
            }
            return
        case "editor":showEditor(slot,id:id);return
        case "capture":
            let delay=stateReadyAt.timeIntervalSinceNow
            if delay>0 {DispatchQueue.main.asyncAfter(deadline:.now()+delay) {handle(request)};return}
            reply(["id":id,"status":"ok","states":try (0..<6).map{try stateData($0).base64EncodedString()}]);return
        case "restore":
            guard let encoded=request["states"] as? [String],(4...6).contains(encoded.count) else {throw HostError(message:"four to six states required")}
            let states=try encoded.map { text -> [String:Any] in
                guard let data=Data(base64Encoded:text),data.count<=4*1024*1024,
                      let value=try PropertyListSerialization.propertyList(from:data,format:nil) as? [String:Any],
                      value["manufacturer"] as? UInt32==fourCC("Tptp"),value["subtype"] as? UInt32==fourCC("Pitl") else {throw HostError(message:"invalid Pistil AU state")}
                return value
            }
            for i in 0..<6 {panic(i);units[i].auAudioUnit.fullState=states[min(i,states.count-1)]}
            stateReadyAt=Date().addingTimeInterval(0.06)
        case "quit":
            for i in 0..<6 {panic(i)}
            engine.stop();reply(["id":id,"status":"ok"]);app.terminate(nil);return
        default:throw HostError(message:"unknown host command")
        }
        if request["id"] != nil {reply(["id":id,"status":"ok"])}
    } catch {reply(["id":id,"status":"error","error":(error as? HostError)?.message ?? error.localizedDescription])}
}
func loadNext() {
    let desc=AudioComponentDescription(componentType:fourCC("aumu"),componentSubType:fourCC("Pitl"),componentManufacturer:fourCC("Tptp"),componentFlags:0,componentFlagsMask:0)
    AVAudioUnit.instantiate(with:desc,options:[.loadInProcess]) { unit,error in
        DispatchQueue.main.async {
            guard let instrument=unit as? AVAudioUnitMIDIInstrument else {
                reply(["event":"host_error","error":error?.localizedDescription ?? "Installed Pistil AU unavailable"]);exit(1)
            }
            let index=units.count
            units.append(instrument)
            engine.attach(instrument)
            let mixer=AVAudioMixerNode();engine.attach(mixer);gains.append(mixer)
            let delay=AVAudioUnitDelay();delay.wetDryMix=0;delay.bypass=true;engine.attach(delay);delays.append(delay)
            let reverb=AVAudioUnitReverb();reverb.loadFactoryPreset(.mediumHall);reverb.wetDryMix=0;reverb.bypass=true
            engine.attach(reverb);reverbs.append(reverb)
            engine.connect(instrument,to:delay,format:nil)
            engine.connect(delay,to:reverb,format:nil)
            engine.connect(reverb,to:mixer,format:nil)
            engine.connect(mixer,to:engine.mainMixerNode,format:nil)
            instrument.auAudioUnit.musicalContextBlock = { tempo, signatureNumerator, signatureDenominator, beat, sampleOffset, downbeat in
                tempo?.pointee=bpm;signatureNumerator?.pointee=4;signatureDenominator?.pointee=4
                beat?.pointee=0;sampleOffset?.pointee=0;downbeat?.pointee=0
                return true
            }
            mixer.installTap(onBus:0,bufferSize:1024,format:nil) { buffer,_ in
                guard let channels=buffer.floatChannelData else {return}
                var peak:Float=0
                for channel in 0..<Int(buffer.format.channelCount) {
                    for frame in 0..<Int(buffer.frameLength) {peak=max(peak,abs(channels[channel][frame]))}
                }
                peakLock.lock();peaks[index]=max(peak,peaks[index]*0.95);peakLock.unlock()
            }
            if units.count<6 {loadNext()} else {
                do {
                    drumSampler=DrumSampler(rate:engine.outputNode.inputFormat(forBus:0).sampleRate)
                    engine.attach(drumSampler.node)
                    engine.attach(drumMixer)
                    engine.connect(drumSampler.node,to:drumMixer,format:AVAudioFormat(standardFormatWithSampleRate:drumSampler.rate,channels:2))
                    engine.connect(drumMixer,to:engine.mainMixerNode,format:nil)
                    engine.mainMixerNode.outputVolume=0
                    try engine.start()
                    DispatchQueue.main.asyncAfter(deadline:.now()+0.75) {
                        ready=true
                        reply(["event":"host_ready","layers":6,"output_enabled":false])
                    }
                } catch {reply(["event":"host_error","error":error.localizedDescription]);exit(1)}
            }
        }
    }
}
let menu=NSMenu()
let item=NSMenuItem();let appMenu=NSMenu();appMenu.addItem(withTitle:"Quit Orchid Studio Pistil",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q");item.submenu=appMenu;menu.addItem(item);app.mainMenu=menu
DispatchQueue.global(qos:.userInteractive).async {
    while let line=readLine() {
        guard let data=line.data(using:.utf8),let request=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] else {continue}
        DispatchQueue.main.async {handle(request)}
    }
    DispatchQueue.main.async {engine.stop();app.terminate(nil)}
}
loadNext()
app.run()
