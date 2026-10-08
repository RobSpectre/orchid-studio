import AVFoundation
import AudioToolbox

// One-shot samples are mixed into the same AVAudioEngine as the Pistil instances.
// Commands carry host-clock deadlines. The audio callback places each attack at
// its exact frame within the render buffer; it never advances a second BPM clock.
final class DrumSampler {
    struct Sample { let left:[Float]; let right:[Float]; let choke:String }
    struct Hit { let sound:String; let at:Double; let gain:Float }
    struct Voice { let sample:Sample; var position:Int; let gain:Float }
    let rate:Double
    let lock=NSLock()
    var samples:[String:Sample]=[:]
    var pending:[Hit]=[]
    var voices:[Voice]=[]
    var volume:Float=0.3
    var reset=false
    var rendered=0
    var late=0
    var maxLate:Double=0
    var peak:Float=0
    var node:AVAudioSourceNode!
    init(rate:Double) {
        self.rate=rate
        let format=AVAudioFormat(standardFormatWithSampleRate:rate,channels:2)!
        node=AVAudioSourceNode(format:format) { [weak self] _,timestamp,frames,abl -> OSStatus in
            guard let self=self else{return noErr}
            let buffers=UnsafeMutableAudioBufferListPointer(abl)
            let left=buffers[0].mData!.assumingMemoryBound(to:Float.self)
            let right=buffers[1].mData!.assumingMemoryBound(to:Float.self)
            let start=AVAudioTime.seconds(forHostTime:timestamp.pointee.mHostTime)
            self.lock.lock()
            if self.reset {self.voices.removeAll();self.reset=false}
            let count=Int(frames)
            var blockPeak:Float=0
            for frame in 0..<count {
                let now=start+Double(frame)/self.rate
                while let hit=self.pending.first,hit.at<=now {
                    self.pending.removeFirst()
                    if let sample=self.samples[hit.sound] {
                        if !sample.choke.isEmpty {self.voices.removeAll{$0.sample.choke==sample.choke}}
                        if self.voices.count>=128 {self.voices.removeFirst()}
                        self.voices.append(Voice(sample:sample,position:0,gain:hit.gain))
                        self.rendered+=1
                        let delay=max(0,now-hit.at)
                        if delay>0.002 {self.late+=1}
                        self.maxLate=max(self.maxLate,delay)
                    }
                }
                var l:Float=0;var r:Float=0
                for i in self.voices.indices {
                    let voice=self.voices[i]
                    if voice.position<voice.sample.left.count {
                        l+=voice.sample.left[voice.position]*voice.gain
                        r+=voice.sample.right[voice.position]*voice.gain
                        self.voices[i].position+=1
                    }
                }
                self.voices.removeAll{$0.position >= $0.sample.left.count}
                left[frame]=l*self.volume;right[frame]=r*self.volume
                blockPeak=max(blockPeak,max(abs(left[frame]),abs(right[frame])))
            }
            self.peak=max(blockPeak,self.peak*0.9)
            self.lock.unlock()
            return noErr
        }
    }
    func load(_ specs:[[String:Any]])throws {
        let format=AVAudioFormat(standardFormatWithSampleRate:rate,channels:2)!
        var loaded:[String:Sample]=[:]
        var totalFrames:Int64=0
        guard specs.count<=92 else{throw HostError(message:"At most 92 sounds")}
        for spec in specs {
            guard let id=spec["id"] as? String, let path=spec["path"] as? String else{throw HostError(message:"Sample needs id and path")}
            let file=try AVAudioFile(forReading:URL(fileURLWithPath:path))
            guard file.length>0,Double(file.length)/file.processingFormat.sampleRate<=30,
                  file.processingFormat.channelCount<=2 else {throw HostError(message:"Samples must be mono/stereo and under 30 seconds")}
            let source=AVAudioPCMBuffer(pcmFormat:file.processingFormat,frameCapacity:AVAudioFrameCount(file.length))!
            try file.read(into:source)
            let capacity=AVAudioFrameCount(ceil(Double(file.length)*rate/file.processingFormat.sampleRate)+64)
            totalFrames+=Int64(capacity)
            guard totalFrames<=Int64(rate*300) else {throw HostError(message:"Loaded samples exceed five minutes")}
            let output=AVAudioPCMBuffer(pcmFormat:format,frameCapacity:capacity)!
            guard let converter=AVAudioConverter(from:source.format,to:format) else {throw HostError(message:"Unsupported sample format")}
            var supplied=false;var conversionError:NSError?
            converter.convert(to:output,error:&conversionError) { _,status in
                if supplied {status.pointee = .endOfStream;return nil}
                supplied=true;status.pointee = .haveData;return source
            }
            if let error=conversionError {throw error}
            guard let channels=output.floatChannelData,output.frameLength>0 else{throw HostError(message:"Empty decoded sample")}
            let gain=Float(spec["gain"] as? Double ?? 1)
            let pan=Float(spec["pan"] as? Double ?? 0)
            let lGain=gain*min(1,1-pan),rGain=gain*min(1,1+pan)
            let count=Int(output.frameLength)
            loaded[id]=Sample(left:(0..<count).map{channels[0][$0]*lGain},right:(0..<count).map{channels[1][$0]*rGain},choke:spec["choke_group"] as? String ?? "")
        }
        lock.lock();samples=loaded;pending.removeAll();reset=true;lock.unlock()
    }
    func hit(_ sound:String,at:Double,gain:Float)throws {
        lock.lock();defer{lock.unlock()}
        guard samples[sound] != nil,at.isFinite,gain.isFinite,(0...1).contains(gain) else {throw HostError(message:"Invalid drum hit")}
        guard pending.count<8192 else {throw HostError(message:"Drum queue is full")}
        pending.append(Hit(sound:sound,at:at,gain:gain));pending.sort{$0.at<$1.at}
    }
    func stop() {lock.lock();pending.removeAll();reset=true;lock.unlock()}
    func setVolume(_ value:Float) {lock.lock();volume=value;lock.unlock()}
    func status()->[String:Any] {
        lock.lock();defer{lock.unlock()}
        return ["sounds":samples.count,"rendered_hits":rendered,"late_hits":late,"max_late_ms":maxLate*1000,"peak":peak,"sample_rate":rate]
    }
}
