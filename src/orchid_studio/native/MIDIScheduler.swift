import AVFoundation
import AudioToolbox

enum MIDISchedulerError: LocalizedError {
    case invalidDeadline, full, renderNotify(OSStatus)
    var errorDescription:String? {
        switch self {
        case .invalidDeadline: return "MIDI deadline must be finite"
        case .full: return "MIDI deadline queue is full"
        case .renderNotify(let code): return "Cannot install MIDI render callback (\(code))"
        }
    }
}

// A bounded, stable min-heap. Storage is allocated once, never in the render callback.
// The producer may wait briefly; the audio thread only tries the lock and otherwise
// leaves events for the next buffer. Overdue events then use offset zero.
final class MIDIDeadlineQueue {
    private struct Event {
        var at:Double = 0
        var order:UInt64 = 0
        var status:UInt32 = 0
        var data1:UInt32 = 0
        var data2:UInt32 = 0
    }
    private let lock=NSLock()
    private let storage:UnsafeMutablePointer<Event>
    private let capacity:Int
    private var count=0
    private var sequence:UInt64=0
    private var rate:Double
    private var panicPending=false
    private var delivered=0, late=0, cancelled=0, errors=0, panics=0
    private var maxLate:Double=0

    init(rate:Double, capacity:Int=8192) {
        precondition(rate.isFinite && rate>0 && capacity>0)
        self.rate=rate;self.capacity=capacity
        storage = .allocate(capacity:capacity)
        storage.initialize(repeating:Event(),count:capacity)
    }
    deinit {storage.deinitialize(count:capacity);storage.deallocate()}

    private func before(_ a:Event,_ b:Event)->Bool {
        a.at<b.at || (a.at==b.at && a.order<b.order)
    }
    func enqueue(at:Double,status:UInt32,data1:UInt32,data2:UInt32)throws {
        guard at.isFinite else {throw MIDISchedulerError.invalidDeadline}
        lock.lock();defer{lock.unlock()}
        guard count<capacity else {throw MIDISchedulerError.full}
        let event=Event(at:at,order:sequence,status:status,data1:data1,data2:data2)
        sequence &+= 1
        var index=count;count+=1
        while index>0 {
            let parent=(index-1)/2
            if !before(event,storage[parent]) {break}
            storage[index]=storage[parent];index=parent
        }
        storage[index]=event
    }
    private func pop()->Event {
        let event=storage[0];count-=1
        if count>0 {
            let tail=storage[count]
            var index=0
            while index*2+1<count {
                var child=index*2+1
                if child+1<count && before(storage[child+1],storage[child]) {child+=1}
                if !before(storage[child],tail) {break}
                storage[index]=storage[child];index=child
            }
            storage[index]=tail
        }
        return event
    }
    func cancelAndPanic() {
        lock.lock();defer{lock.unlock()}
        cancelled+=count;count=0;panicPending=true
    }
    func setSampleRate(_ value:Double) {
        precondition(value.isFinite && value>0)
        lock.lock();rate=value;lock.unlock()
    }
    func render(start:Double,frames:UInt32,
                send:(UInt32,UInt32,UInt32,UInt32)->OSStatus) {
        guard start.isFinite,frames>0,lock.try() else {return}
        defer{lock.unlock()}
        if panicPending {
            // Same pre-render callback as note delivery: no queued note can overtake this.
            for channel:UInt32 in 0..<16 {
                for index in 0..<4 {
                    let controller:UInt32 = index==0 ? 64 : index==1 ? 66 : index==2 ? 123 : 120
                    if send(0xB0|channel,controller,0,0) != noErr {errors+=1}
                }
            }
            panicPending=false;panics+=1
        }
        let end=start+Double(frames)/rate
        while count>0 && storage[0].at<end {
            let event=pop()
            let delta=event.at-start
            // Check bounds in floating point before converting. In particular, old
            // or extreme finite deadlines must never become unsigned sample offsets.
            let offset=UInt32(min(Double(frames-1),max(0,delta*rate)))
            if delta<0 {late+=1;maxLate=min(Double.greatestFiniteMagnitude/1000,max(maxLate,-delta))}
            if send(event.status,event.data1,event.data2,offset) != noErr {errors+=1}
            delivered+=1
        }
    }
    func snapshot()->[String:Any] {
        lock.lock();defer{lock.unlock()}
        return ["queued":count,"delivered":delivered,"late_events":late,
                "max_late_ms":maxLate*1000,"cancelled":cancelled,
                "delivery_errors":errors,"panics":panics,"panic_pending":panicPending,
                "sample_rate":rate]
    }
}

// Pistil is an AUv2. Feed MusicDeviceMIDIEvent only bounded offsets in its *current*
// pre-render callback. Absolute timestamps derived from lastRenderTime can become
// stale before delivery and cause Pistil 1.0.2 to overrun its audio output buffer.
final class MIDIRenderScheduler {
    let queue:MIDIDeadlineQueue
    private let unit:AudioUnit
    private static let notify:AURenderCallback = { context,flags,time,_,frames,_ in
        guard flags.pointee.contains(.unitRenderAction_PreRender) else {return noErr}
        let scheduler=Unmanaged<MIDIRenderScheduler>.fromOpaque(context).takeUnretainedValue()
        let hostTime=time.pointee.mFlags.contains(.hostTimeValid) ? time.pointee.mHostTime : mach_absolute_time()
        scheduler.queue.render(start:AVAudioTime.seconds(forHostTime:hostTime),frames:frames) {
            MusicDeviceMIDIEvent(scheduler.unit,$0,$1,$2,$3)
        }
        return noErr
    }
    init(unit:AudioUnit,rate:Double)throws {
        self.unit=unit;queue=MIDIDeadlineQueue(rate:rate)
        let result=AudioUnitAddRenderNotify(unit,Self.notify,Unmanaged.passUnretained(self).toOpaque())
        guard result==noErr else {throw MIDISchedulerError.renderNotify(result)}
    }
    deinit {AudioUnitRemoveRenderNotify(unit,Self.notify,Unmanaged.passUnretained(self).toOpaque())}
}
