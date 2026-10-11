import Foundation

@main
struct MIDISchedulerTests {
    static func main() throws {
        typealias Delivery=(UInt32,UInt32,UInt32,UInt32)
        var sent:[Delivery]=[]
        func receive(_ status:UInt32,_ note:UInt32,_ value:UInt32,_ offset:UInt32)->Int32 {
            sent.append((status,note,value,offset));return 0
        }
        let q=MIDIDeadlineQueue(rate:1024)
        try q.enqueue(at:10.5,status:144,data1:64,data2:32) // next buffer, not this one
        try q.enqueue(at:10.25,status:128,data1:60,data2:0)
        try q.enqueue(at:10.25,status:144,data1:60,data2:32) // preserve retrigger ordering
        try q.enqueue(at:10-1.0/1024,status:144,data1:61,data2:32) // regression: one sample late
        q.render(start:10,frames:512,send:receive)
        assert(sent.count==3 && sent[0].1==61 && sent[0].3==0)
        assert(sent[1].0==128 && sent[2].0==144 && sent[1].3==256 && sent[2].3==256)
        assert(q.snapshot()["queued"] as? Int==1)
        q.render(start:10.5,frames:512,send:receive)
        assert(sent.count==4 && sent[3].1==64 && sent[3].3==0)

        // Panic cancels even very distant notes, sends pedal/voice releases on all
        // channels, and precedes fresh input received after the cancellation.
        try q.enqueue(at:10000,status:144,data1:65,data2:32)
        q.cancelAndPanic()
        try q.enqueue(at:11,status:144,data1:66,data2:32)
        sent=[];q.render(start:11,frames:512,send:receive)
        assert(sent.count==65 && sent.last!.1==66)
        for ch in 0..<16 {
            assert(Array(sent[(ch*4)..<(ch*4+4)]).map{$0.1}==[64,66,123,120])
            assert(sent[ch*4].0==UInt32(176+ch))
        }
        sent=[];q.render(start:10000,frames:512,send:receive);assert(sent.isEmpty)
        assert(q.snapshot()["cancelled"] as? Int==1)

        // A new output format uses the instrument's new rate; no old sample
        // position survives a route transition.
        q.setSampleRate(2048)
        try q.enqueue(at:20.125,status:144,data1:67,data2:32)
        q.render(start:20,frames:512,send:receive)
        assert(sent.last!.3==256)

        // Reject invalid times and overload without silently losing note-offs.
        let bounded=MIDIDeadlineQueue(rate:44100,capacity:1)
        for at in [Double.nan,Double.infinity,-Double.infinity] {
            do {try bounded.enqueue(at:at,status:144,data1:1,data2:1);assertionFailure("accepted invalid deadline")}
            catch MIDISchedulerError.invalidDeadline {} catch {throw error}
        }
        try bounded.enqueue(at:0,status:128,data1:1,data2:0)
        do {try bounded.enqueue(at:1,status:128,data1:2,data2:0);assertionFailure("accepted overflow")}
        catch MIDISchedulerError.full {} catch {throw error}
        sent=[];bounded.render(start:1,frames:1,send:receive)
        assert(sent.count==1 && sent[0].3==0)

        // Extreme finite stale input also clamps safely; diagnostics stay JSON-safe.
        try bounded.enqueue(at:-Double.greatestFiniteMagnitude,status:128,data1:1,data2:0)
        bounded.render(start:Double.greatestFiniteMagnitude,frames:512,send:receive)
        assert(sent.last!.3==0)
        assert(JSONSerialization.isValidJSONObject(bounded.snapshot()))

        // Shuffled deadlines stress heap order and strict bounds across many buffers.
        let stress=MIDIDeadlineQueue(rate:1024,capacity:2048)
        for n in (0..<2048).reversed() {
            try stress.enqueue(at:30+Double(n)/1024,status:144,data1:UInt32(n),data2:1)
        }
        sent=[]
        for block in 0..<16 {stress.render(start:30+Double(block)/8,frames:128,send:receive)}
        assert(sent.count==2048 && sent.map{$0.1}==Array(0..<2048).map{UInt32($0)})
        assert(sent.allSatisfy{$0.3<128})
        assert(stress.snapshot()["queued"] as? Int==0)
        print("MIDI scheduler regression checks passed")
    }
}
