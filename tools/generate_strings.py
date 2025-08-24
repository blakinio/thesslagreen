import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REG = ROOT / 'custom_components' / 'thessla_green_modbus' / 'registers' / 'thessla_green_registers_full.json'
STRINGS = ROOT / 'custom_components' / 'thessla_green_modbus' / 'strings.json'
EN = ROOT / 'custom_components' / 'thessla_green_modbus' / 'translations' / 'en.json'
PL = ROOT / 'custom_components' / 'thessla_green_modbus' / 'translations' / 'pl.json'
SPECIAL_PATH = ROOT / 'custom_components' / 'thessla_green_modbus' / 'options' / 'special_modes.json'


def build():
    regs = {r['name']: r for r in json.loads(REG.read_text(encoding='utf-8'))['registers']}
    baud = [str(v) for v in regs['uart0_baud']['enum'].values()]
    baud_opt = {f'thessla_green_modbus.modbus_baud_rate_{v}': v for v in baud}
    parity_map = {'brak': ('none','None','Brak'), 'parzysty': ('even','Even','Parzysta'), 'nieparzysty': ('odd','Odd','Nieparzysta')}
    parity_en = {f"thessla_green_modbus.modbus_parity_{parity_map[v][0]}": parity_map[v][1] for v in regs['uart0_parity']['enum'].values()}
    parity_pl = {f"thessla_green_modbus.modbus_parity_{parity_map[v][0]}": parity_map[v][2] for v in regs['uart0_parity']['enum'].values()}
    stop_map = {'jeden': ('1','1'), 'dwa': ('2','2')}
    stop_opt = {f"thessla_green_modbus.modbus_stop_bits_{stop_map[v][0]}": stop_map[v][1] for v in regs['uart0_stop']['enum'].values()}
    port_opt = {'thessla_green_modbus.modbus_port_air_b':'Air-B','thessla_green_modbus.modbus_port_air_plus':'Air++'}
    spec_keys = json.loads(SPECIAL_PATH.read_text(encoding='utf-8'))
    spec_en = {'none':'None','boost':'Boost','eco':'Eco','away':'Away','sleep':'Sleep','fireplace':'Fireplace','hood':'Hood','party':'Party','bathroom':'Bathroom','kitchen':'Kitchen','summer':'Summer','winter':'Winter'}
    spec_pl = {'none':'Brak','boost':'Boost','eco':'Eco','away':'Nieobecność','sleep':'Sen','fireplace':'Kominek','hood':'Okap','party':'Impreza','bathroom':'Łazienka','kitchen':'Kuchnia','summer':'Lato','winter':'Zima'}
    spec_en_opt = {k: spec_en[k.split('.')[-1].replace('special_mode_','')] for k in spec_keys}
    spec_pl_opt = {k: spec_pl[k.split('.')[-1].replace('special_mode_','')] for k in spec_keys}
    return {
        'baud_rate': (baud_opt, baud_opt),
        'parity': (parity_en, parity_pl),
        'stop_bits': (stop_opt, stop_opt),
        'port': (port_opt, port_opt),
        'special_mode': (spec_en_opt, spec_pl_opt),
    }


def write():
    strings = json.loads(STRINGS.read_text(encoding='utf-8'))
    en = json.loads(EN.read_text(encoding='utf-8'))
    pl = json.loads(PL.read_text(encoding='utf-8'))
    opts = build()
    def apply(obj, lang):
        fields = obj['services']['set_modbus_parameters']['fields']
        fields['baud_rate']['selector']['select']['options'] = opts['baud_rate'][0]
        fields['parity']['selector']['select']['options'] = opts['parity'][0 if lang=='en' else 1]
        fields['port']['selector']['select']['options'] = opts['port'][0]
        fields['stop_bits']['selector']['select']['options'] = opts['stop_bits'][0]
        obj['services']['set_special_mode']['fields']['mode']['selector']['select']['options'] = opts['special_mode'][0 if lang=='en' else 1]
    apply(strings,'en')
    apply(en,'en')
    apply(pl,'pl')
    STRINGS.write_text(json.dumps(strings, indent=2, ensure_ascii=False)+'\n',encoding='utf-8')
    EN.write_text(json.dumps(en, indent=2, ensure_ascii=False)+'\n',encoding='utf-8')
    PL.write_text(json.dumps(pl, indent=2, ensure_ascii=False)+'\n',encoding='utf-8')


if __name__ == '__main__':
    write()
