"""Join counted source references; never replace a missing player or coach."""
def bind(data, team_table, current):
    digest=data['source_sha256']
    if team_table['source_sha256']!=digest or current['source_sha256']!=digest:
        raise ValueError('Generation inputs belong to different saves')
    players={p['unique_id']:p for p in data['players']if p['unique_id']is not None}
    staff={s['person_selector']:s for s in data['staff']}
    selections={r['team_id']:r for r in current['records']}
    result=[]
    for team in team_table['records']:
        club=next(c for c in data['clubs']if any(t['team_id']==team['team_id']for t in c['teams']))
        coach=staff.get(team['coach_person_reference'])
        if coach is None or coach['club_uid']!=club['uid']:raise ValueError('Unresolved source coach reference')
        selection=selections.get(team['team_id'])
        if selection is None:raise ValueError('Missing source selection')
        roster=[];stale_bench=[]
        for slot,selector in enumerate(selection['player_selectors']):
            if selector==0xffffffff:
                if slot<11:raise ValueError('Incomplete source starting eleven')
                continue
            uid=data['player_selectors'].get(str(selector));player=players.get(uid)
            if player is None or player['club_uid']!=club['uid']:
                if slot<11:raise ValueError('Unresolved or foreign source starting player')
                stale_bench.append({'slot':slot,'person_selector':selector,'source_uid':uid,'reason':'not_in_current_club'})
                continue
            roster.append({'source_slot':slot,'person_selector':selector,'player':player,
                           'first_team_member':selector in team['member_references']})
        if len({r['player']['unique_id']for r in roster})!=len(roster):raise ValueError('Duplicate source player')
        result.append({'source_sha256':digest,'team':team,'club':club,'coach':coach,'roster':roster,
                       'current_selection':selection,'excluded_stale_bench':stale_bench,'full_opponent_recovered':False})
    return result
