"""Render local Hydrogen sample assets in Studio's existing native audio host."""
import xml.etree.ElementTree as ET


class NativeDrumAudio:
    native_audio = True
    def __init__(self, router, library):
        self.router=router
        self.library=library
        self.volume=.3
        self.muted=False
        self.sounds=[]

    @property
    def host(self):
        if not self.router.host:
            raise ValueError('enable the native Studio audio host before loading drum sounds')
        return self.router.host

    def load(self):
        # The native host can start without Hydrogen or an installed drum kit.
        # Beat playback validates its required sounds separately.
        specs=[]
        for sound in self.library.sounds.values():
            root=ET.fromstring(sound['instrument'])
            filenames=list(root.iter('filename'))
            if len(filenames)!=1:
                raise ValueError(f"{sound['name']}: native drums currently support one-shot, single-sample instruments")
            pitch=float(root.findtext('pitchOffset') or 0)
            layer=root.find('.//layer')
            if pitch or (layer is not None and float(layer.findtext('pitch') or 0)):
                raise ValueError(f"{sound['name']}: bake pitch changes into the sample before importing")
            gain=float(root.findtext('volume') or 1)*float(root.findtext('gain') or 1)
            if layer is not None:gain*=float(layer.findtext('gain') or 1)
            specs.append({'id':sound['id'],'path':filenames[0].text,'gain':gain,'pan':float(root.findtext('pan') or 0),
                          'choke_group':sound.get('kit','')+':'+root.findtext('muteGroup') if root.findtext('muteGroup') not in (None,'-1') else ''})
        self.host.call('drum-load',sounds=specs)
        self.sounds=[s['id'] for s in specs]
        return {'status':'ok','engine':'studio-native','sounds':len(specs)}

    def command(self, action, value=None, strip=None):
        if action in ('stop','pause','mute') and (not self.router.host or self.router.host.error):
            return {'status':'ok','engine':'studio-native'}
        host=self.host
        if action=='note-on':
            index=strip-36
            if not 0<=index<len(self.sounds):raise ValueError('unknown sample index')
            host.call('drum-hit',sound=self.sounds[index],velocity=value,wait=False)
        elif action in ('stop','pause'):
            host.call('drum-stop')
        elif action in ('volume','mute','unmute'):
            if action=='volume':self.volume=value
            if action=='mute':self.muted=True
            if action=='unmute':self.muted=False
            host.call('drum-volume',volume=0 if self.muted else self.volume)
        else:
            raise ValueError('native drum controls: volume, mute, unmute, stop; edit lane sounds/volume in the beat')
        return {'status':'ok','engine':'studio-native'}

    def feedback(self):
        return self.host.call('status')['drums']
