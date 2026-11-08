"""Selective full player decoding, using the reader's registered layouts.

A light identity/registration scan covers the database. Full names, attributes,
contracts and personality are decoded only for requested club registrations.
"""
import struct
from collections import Counter

def selected_players(save, clubs, roster_only=False):
    from fmsave._layouts import find_layout,PersonBlockLayout,ContractLayout
    from fmsave.readers.players import build_player_decoder
    from fmsave.readers.player_scan import window_end,closing_person_header
    context=save._context;info=save.info
    if info.game_date is None:raise ValueError('存档日期无法读取')
    save.clubs()  # Original club identity checks remain enforced.
    schema=info.section_schemas['game_db']
    with context.section('game_db')as db:
        records=context.player_records();index=context.club_index();names=context.name_pools()
        decoder=build_player_decoder(records.layout,index,names,info.game_date,
            find_layout(PersonBlockLayout,'game_db',schema,info.build).layout,
            find_layout(ContractLayout,'game_db',schema,info.build).layout,info.file_name)
        header=decoder.header_layout;layout=records.layout
        selected=[];identities={};counts=Counter();first=Counter();local_ids={};seen=set()
        total=len(records.record_offsets)
        for pos,offset in enumerate(records.record_offsets):
            end=window_end(records,pos,len(db));values=header.struct_object.unpack_from(db,offset+header.start_offset)
            team=values[header.team_id_index];fields=decoder.team_fields.get(team)
            club=fields[0]if fields else None;slot=fields[7]if fields else None
            counts[str(club)]+=1
            if slot==0:first[str(club)]+=1
            # The initial import validates the complete identity map. A roster
            # request only needs closing identities/full attributes of selected
            # clubs; do not redo that work for every unrelated player.
            if roster_only and club not in clubs:continue
            uid=records.uids[pos];ceiling=records.uids[pos+1]if pos+1<total else None
            closing=closing_person_header(db,records.pindexes[pos],offset+layout.decode_extent,end,uid,ceiling)
            unique=closing[1]if closing else None
            local_ids[uid]=unique
            if unique is not None:
                if unique in seen:raise ValueError('球员唯一ID重复')
                seen.add(unique);identities[str(unique)]=club
            if club not in clubs:continue
            player,_=decoder.decode(db,offset,end,is_last_record=pos+1==total,suspension_entries=None)
            if player.unique_id!=unique or player.club_uid!=club or player.team_slot!=slot:raise ValueError('球员索引与完整解码身份不一致')
            if len(player.positions.__dataclass_fields__)!=15 or len(player.raw_attributes.__dataclass_fields__)!=52:raise ValueError('球员属性布局不匹配')
            selected.append(player)
        return selected,identities,dict(counts),{c:first[c]for c in counts},local_ids
