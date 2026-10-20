"""Apply the reviewed weapon-balance CSV to runtime catalogs. Run from game/."""
import argparse
import csv
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=Path('../docs/gameplay/WEAPON_BALANCE.csv'))
    args = parser.parse_args()
    weapon_path = Path('data/weapons/catalog.json')
    map_path = Path('data/maps/catalog.json')
    catalog = json.loads(weapon_path.read_text(encoding='utf-8'))
    maps = json.loads(map_path.read_text(encoding='utf-8'))
    by_title = {value['title'].lower(): value for value in catalog['weapons'].values()}
    seen = set()
    with args.csv.open(encoding='utf-8-sig', newline='') as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        identity = (row['weapon'], row['fire_mode'], row['map'])
        if identity in seen:
            raise ValueError('Duplicate row: '+str(identity))
        seen.add(identity)
        expected_basis = ('per_second' if row['fire_mode'] == 'Primary' and row['weapon'] in ('Lightning gun','Flamethrower')
                          else 'per_pellet' if row['weapon'] == 'Flak cannon' else 'per_hit')
        if row['damage_basis'] != expected_basis:
            raise ValueError('Unsupported damage basis: '+str(identity))
        def number(key):
            value = float(row[key])
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Expected positive finite '+key+': '+str(identity))
            return value
        if row['weapon'] == 'Pulse gun':
            profile = next(m['pulse_gun'] for m in maps['maps'] if m['id'] == row['map'])
            profile.update(damage=number('damage'), interval=1/number('fire_rate_per_s'),
                           range=number('range_m'), speed=number('projectile_speed_m_per_s'))
            continue
        profile = by_title[row['weapon'].lower()]
        secondary = row['fire_mode'].startswith('Secondary')
        if secondary:
            prefix = 'scoped_' if row['weapon'] in ('Rifle','Rocket launcher') else 'secondary_'
            profile[prefix+'interval'] = 1/number('fire_rate_per_s')
            profile[prefix+'damage'] = number('damage')
            profile[prefix+'range'] = number('range_m')
            if row['projectile_speed_m_per_s']:
                profile[prefix+'projectile_speed'] = number('projectile_speed_m_per_s')
            if row['headshot_damage']:
                profile['headshot_damage'] = number('headshot_damage')
        else:
            profile['damage'] = number('damage')
            if row['fire_rate_per_s']:
                profile['interval'] = 1/number('fire_rate_per_s')
            if row['weapon'] == 'Flamethrower':
                # CSV range is the full-damage reach; retain the approved 5 m tail.
                profile['full_damage_range'] = number('range_m')
                profile['range'] = number('range_m')+5
            else:
                profile['range'] = number('range_m')
            if row['weapon'] == 'EMP gun':
                profile['full_damage_range'] = 20
            for column, key in [('projectile_speed_m_per_s','projectile_speed'),
                                ('damage_tick_interval_s','damage_tick'),
                                ('pellets_per_shot','pellets'),('splash_damage_max','splash_damage'),
                                ('splash_radius_m','splash_radius'),('dot_duration_s','dot_duration')]:
                if row[column]:
                    profile[key] = number(column)
            if row['dot_damage_per_s']:
                profile['dot_damage'] = number('dot_damage_per_s')*profile.get('dot_interval',1)
    if len(rows) != 16:
        raise ValueError('Expected all 16 firing-mode/map rows')
    for path, data in [(weapon_path,catalog),(map_path,maps)]:
        path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print('Applied 16 weapon-balance rows to runtime catalogs')


if __name__ == '__main__':
    main()
