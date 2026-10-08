"""Pure drum-editor operations shared by API clients; saving is explicit."""
import copy
from .drum_library import validate
from .sequencer import integer, number

ACTIONS=('clone','new','rename','resize','swing','lane-add','lane-set','step','clear-bar','copy-bar','repeat-bar')


def edit(document, request, sounds):
    original=validate(document,sounds);d=copy.deepcopy(original)
    action=request.get('action')
    if action not in ACTIONS:raise ValueError('action must be '+', '.join(ACTIONS))
    def bar(name='bar'):
        return integer(request.get(name),1,d['bars'],name)-1
    if action in ('clone','new'):
        if request.get('new_id')==d['id']:raise ValueError('choose a new ID to preserve the source beat')
        d['id']=request.get('new_id');d['name']=request.get('name')
        if action=='new':d.update(hits=[],swing=0,genre='custom')
    elif action=='rename':d['name']=request.get('name')
    elif action=='resize':
        bars=integer(request.get('bars'),1,64,'bars');old=d['bars'];hits=d['hits'];d['bars']=bars
        d['hits']=[{**h,'beat':h['beat']+offset} for offset in range(0,bars*4,old*4) for h in hits if h['beat']+offset<bars*4]
    elif action=='swing':d['swing']=request.get('swing')
    elif action=='lane-add':d['lanes'].append(copy.deepcopy(request.get('lane')))
    elif action=='lane-set':
        lane=next((x for x in d['lanes'] if x['id']==request.get('lane')),None)
        if lane is None:raise ValueError('unknown lane')
        changes=request.get('settings')
        if not isinstance(changes,dict) or not changes or set(changes)-{'name','sound','gain','muted'}:raise ValueError('lane settings: name, sound, gain, muted')
        lane.update(changes)
    elif action=='step':
        lane=request.get('lane')
        if not any(x['id']==lane for x in d['lanes']):raise ValueError('unknown lane')
        onset=bar()*4+(integer(request.get('step'),1,16,'step')-1)/4
        hits=[h for h in d['hits'] if h['lane']==lane and onset-1e-8<=h['beat']<onset+.25-1e-8]
        mode=request.get('mode','toggle')
        if mode not in ('toggle','set','remove','accent'):raise ValueError('step mode: toggle, set, remove, accent')
        if mode=='accent' and hits:
            hits[0]['velocity']=.55 if hits[0]['velocity']>=.75 else .9
        else:
            d['hits']=[h for h in d['hits'] if h not in hits]
            if mode in ('set','accent') or (mode=='toggle' and not hits):
                d['hits'].append({'lane':lane,'beat':onset,'velocity':request.get('velocity',.9 if mode=='accent' else .6),'probability':request.get('probability',1)})
    else:
        index=bar();hits=[h for h in d['hits'] if index*4<=h['beat']<(index+1)*4]
        if action=='repeat-bar':
            d['hits']=[{**h,'beat':h['beat']-index*4+i*4} for i in range(d['bars']) for h in hits]
        else:
            target=bar('target_bar') if action=='copy-bar' else index
            d['hits']=[h for h in d['hits'] if not target*4<=h['beat']<(target+1)*4]
            if action=='copy-bar':d['hits'].extend({**h,'beat':h['beat']+(target-index)*4} for h in hits)
    return {'document':validate(d,sounds),'undo_document':original,'saved':False,
            'next':'Keep undo_document for draft undo; beat-save publishes document'}
