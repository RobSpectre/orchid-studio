// Explicit integration test for the user's installed AU. Renders only into memory;
// never starts an output device, opens MIDI ports, or changes saved user patches.
// Compile alongside src/orchid_studio/native/MIDIScheduler.swift on macOS.
import AppKit
import AVFoundation
import AudioToolbox

@main
struct PistilMIDISmoke {
    static func main() {
        let app=NSApplication.shared
        app.setActivationPolicy(.prohibited)
        func fourCC(_ s:String)->UInt32 {s.utf8.reduce(0){($0<<8)|UInt32($1)}}
        let desc=AudioComponentDescription(componentType:fourCC("aumu"),componentSubType:fourCC("Pitl"),componentManufacturer:fourCC("Tptp"),componentFlags:0,componentFlagsMask:0)
        AVAudioUnit.instantiate(with:desc,options:[.loadInProcess]) { unit,error in
            DispatchQueue.main.async {
                guard let instrument=unit as? AVAudioUnitMIDIInstrument else {
                    fputs("Pistil unavailable: \(String(describing:error))\n",stderr);exit(2)
                }
                DispatchQueue.main.asyncAfter(deadline:.now()+1) {
                    do {
                        for rate in [44100.0,48000.0] {try run(instrument,rate:rate)}
                        print("Pistil offline late-MIDI and cancellation checks passed")
                        exit(0)
                    } catch {fputs("\(error)\n",stderr);exit(3)}
                }
            }
        }
        app.run()
    }
    static func run(_ instrument:AVAudioUnitMIDIInstrument,rate:Double)throws {
        let au=instrument.auAudioUnit
        au.deallocateRenderResources()
        let format=AVAudioFormat(standardFormatWithSampleRate:rate,channels:2)!
        try au.outputBusses[0].setFormat(format)
        let scheduler=try MIDIRenderScheduler(unit:instrument.audioUnit,rate:rate)
        try au.allocateRenderResources()
        defer {au.deallocateRenderResources();withExtendedLifetime(scheduler) {}}
        let buffer=AVAudioPCMBuffer(pcmFormat:format,frameCapacity:512)!
        var frame=0
        let origin=AVAudioTime.seconds(forHostTime:mach_absolute_time())
        func render(_ frames:UInt32=512)throws {
            var flags=AudioUnitRenderActionFlags()
            var stamp=AudioTimeStamp()
            stamp.mSampleTime=Double(frame)
            stamp.mHostTime=AVAudioTime.hostTime(forSeconds:origin+Double(frame)/rate)
            stamp.mFlags=[.sampleTimeValid,.hostTimeValid]
            buffer.frameLength=frames
            let result=AudioUnitRender(instrument.audioUnit,&flags,&stamp,0,frames,buffer.mutableAudioBufferList)
            assert(result==noErr,"render failed: \(result)")
            frame+=Int(frames)
        }
        for _ in 0..<4 {try render()}
        // Reproduce the one-sample-late deadline without giving it to the AU as
        // a stale absolute timestamp. The installed pre-render callback must deliver it.
        try scheduler.queue.enqueue(at:origin+Double(frame-1)/rate,status:144,data1:60,data2:32)
        try render()
        assert(scheduler.queue.snapshot()["delivered"] as? Int==1)
        assert(scheduler.queue.snapshot()["late_events"] as? Int==1)
        // A future note-off stays queued until its buffer; overdue bursts remain safe.
        try scheduler.queue.enqueue(at:origin+Double(frame+1024)/rate,status:128,data1:60,data2:0)
        try render(128)
        assert(scheduler.queue.snapshot()["queued"] as? Int==1)
        for n in 0..<2000 {
            try scheduler.queue.enqueue(at:origin-0.1,status:n%2==0 ? 144 : 128,data1:UInt32(48+n%12),data2:n%2==0 ? 24 : 0)
            if n%16==15 {try render()}
        }
        for _ in 0..<4 {try render()}
        assert(scheduler.queue.snapshot()["queued"] as? Int==0)
        let delivered=scheduler.queue.snapshot()["delivered"] as! Int
        try scheduler.queue.enqueue(at:origin+10000,status:144,data1:72,data2:32)
        scheduler.queue.cancelAndPanic()
        try render()
        assert(scheduler.queue.snapshot()["delivered"] as? Int==delivered)
        assert(scheduler.queue.snapshot()["cancelled"] as? Int==1)
        assert(scheduler.queue.snapshot()["panics"] as? Int==1)
        assert(scheduler.queue.snapshot()["delivery_errors"] as? Int==0)
        print("rate=\(rate) \(scheduler.queue.snapshot())")
    }
}
