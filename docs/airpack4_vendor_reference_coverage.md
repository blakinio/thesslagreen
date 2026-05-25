# AirPack4 Vendor Reference Coverage Report

## Summary

| Metric | Count |
|--------|-------|
| Vendor total registers | 353 |
| Integration total registers | 357 |
| Common (vendor ∩ integration) | 353 |
| Missing from integration | 0 |
| Extras in integration (not in vendor) | 4 |
| Name mismatches (same address, different name) | 299 |
| Vendor duplicate addresses | 0 |

## Counts per Function Code

| FC | Vendor | Integration |
|----|--------|-------------|
| FC01 | 8 | 8 |
| FC02 | 16 | 16 |
| FC03 | 302 | 304 |
| FC04 | 27 | 29 |

## Missing from Integration

None — all vendor registers are present in the integration.

## Extras in Integration (not in vendor reference)

| FC | Address (hex) | Address (dec) | Integration name | Known intentional | Reason |
|-----|--------------|--------------|------------------|-------------------|--------|
| FC03 | 0x20fa | 8442 | e_250 | yes | firmware-observed alarm: filter replacement required (unit without pressure switch); kept as real-device extra |
| FC03 | 0x20fc | 8444 | e_252 | yes | firmware-observed alarm: filter replacement required (unit with pressure switch); kept as real-device extra |
| FC04 | 0x17 | 23 | heating_temperature | yes | heating_temperature — TH sensor on AirPack4 h/v units |
| FC04 | 0x12a | 298 | water_removal_active | yes | water_removal_active — HEWR procedure flag, series 4 |

## Name Mismatches (same address, different name)

Total: 299 mismatches — typo_normalization: 150, legacy_stable: 2, probable_mismatch: 147

> **Policy**: Integration register names are stable legacy names. They MUST NOT be renamed as that would break existing entity IDs, unique IDs, and service names. Name mismatches are expected and benign.

| FC | Address (hex) | Vendor name | Integration name | Classification |
|-----|--------------|-------------|-----------------|----------------|
| FC01 | 0x5 | duct_warter_heater_pump | duct_water_heater_pump | probable_mismatch |
| FC01 | 0xd | workt_permit | work_permit | probable_mismatch |
| FC01 | 0xf | hood | hood_output | probable_mismatch |
| FC02 | 0x4 | hood | hood_switch | probable_mismatch |
| FC02 | 0xf | ppoz | fire_alarm | probable_mismatch |
| FC03 | 0x0 | date_time_year_month | date_time | probable_mismatch |
| FC03 | 0x1 | date_time_day_weekday | date_time_ddtt | probable_mismatch |
| FC03 | 0x2 | date_time_hour_minute | date_time_ggmm | probable_mismatch |
| FC03 | 0x3 | date_time_second_csec | date_time_sscc | probable_mismatch |
| FC03 | 0x7 | lock_date_year | lock_date | probable_mismatch |
| FC03 | 0x8 | lock_date_month | lock_date_00mm | probable_mismatch |
| FC03 | 0x9 | lock_date_day | lock_date_00dd | probable_mismatch |
| FC03 | 0x10 | schedule_summer_mon_slot1_time | schedule_summer_mon_1 | probable_mismatch |
| FC03 | 0x11 | schedule_summer_mon_slot2_time | schedule_summer_mon_2 | probable_mismatch |
| FC03 | 0x12 | schedule_summer_mon_slot3_time | schedule_summer_mon_3 | probable_mismatch |
| FC03 | 0x13 | schedule_summer_mon_slot4_time | schedule_summer_mon_4 | probable_mismatch |
| FC03 | 0x14 | schedule_summer_tue_slot1_time | schedule_summer_tue_1 | probable_mismatch |
| FC03 | 0x15 | schedule_summer_tue_slot2_time | schedule_summer_tue_2 | probable_mismatch |
| FC03 | 0x16 | schedule_summer_tue_slot3_time | schedule_summer_tue_3 | probable_mismatch |
| FC03 | 0x17 | schedule_summer_tue_slot4_time | schedule_summer_tue_4 | probable_mismatch |
| FC03 | 0x18 | schedule_summer_wed_slot1_time | schedule_summer_wed_1 | probable_mismatch |
| FC03 | 0x19 | schedule_summer_wed_slot2_time | schedule_summer_wed_2 | probable_mismatch |
| FC03 | 0x1a | schedule_summer_wed_slot3_time | schedule_summer_wed_3 | probable_mismatch |
| FC03 | 0x1b | schedule_summer_wed_slot4_time | schedule_summer_wed_4 | probable_mismatch |
| FC03 | 0x1c | schedule_summer_thu_slot1_time | schedule_summer_thu_1 | probable_mismatch |
| FC03 | 0x1d | schedule_summer_thu_slot2_time | schedule_summer_thu_2 | probable_mismatch |
| FC03 | 0x1e | schedule_summer_thu_slot3_time | schedule_summer_thu_3 | probable_mismatch |
| FC03 | 0x1f | schedule_summer_thu_slot4_time | schedule_summer_thu_4 | probable_mismatch |
| FC03 | 0x20 | schedule_summer_fri_slot1_time | schedule_summer_fri_1 | probable_mismatch |
| FC03 | 0x21 | schedule_summer_fri_slot2_time | schedule_summer_fri_2 | probable_mismatch |
| FC03 | 0x22 | schedule_summer_fri_slot3_time | schedule_summer_fri_3 | probable_mismatch |
| FC03 | 0x23 | schedule_summer_fri_slot4_time | schedule_summer_fri_4 | probable_mismatch |
| FC03 | 0x24 | schedule_summer_sat_slot1_time | schedule_summer_sat_1 | probable_mismatch |
| FC03 | 0x25 | schedule_summer_sat_slot2_time | schedule_summer_sat_2 | probable_mismatch |
| FC03 | 0x26 | schedule_summer_sat_slot3_time | schedule_summer_sat_3 | probable_mismatch |
| FC03 | 0x27 | schedule_summer_sat_slot4_time | schedule_summer_sat_4 | probable_mismatch |
| FC03 | 0x28 | schedule_summer_sun_slot1_time | schedule_summer_sun_1 | probable_mismatch |
| FC03 | 0x29 | schedule_summer_sun_slot2_time | schedule_summer_sun_2 | probable_mismatch |
| FC03 | 0x2a | schedule_summer_sun_slot3_time | schedule_summer_sun_3 | probable_mismatch |
| FC03 | 0x2b | schedule_summer_sun_slot4_time | schedule_summer_sun_4 | probable_mismatch |
| FC03 | 0x2c | schedule_winter_mon_slot1_time | schedule_winter_mon_1 | probable_mismatch |
| FC03 | 0x2d | schedule_winter_mon_slot2_time | schedule_winter_mon_2 | probable_mismatch |
| FC03 | 0x2e | schedule_winter_mon_slot3_time | schedule_winter_mon_3 | probable_mismatch |
| FC03 | 0x2f | schedule_winter_mon_slot4_time | schedule_winter_mon_4 | probable_mismatch |
| FC03 | 0x30 | schedule_winter_tue_slot1_time | schedule_winter_tue_1 | probable_mismatch |
| FC03 | 0x31 | schedule_winter_tue_slot2_time | schedule_winter_tue_2 | probable_mismatch |
| FC03 | 0x32 | schedule_winter_tue_slot3_time | schedule_winter_tue_3 | probable_mismatch |
| FC03 | 0x33 | schedule_winter_tue_slot4_time | schedule_winter_tue_4 | probable_mismatch |
| FC03 | 0x34 | schedule_winter_wed_slot1_time | schedule_winter_wed_1 | probable_mismatch |
| FC03 | 0x35 | schedule_winter_wed_slot2_time | schedule_winter_wed_2 | probable_mismatch |
| ... | ... | ... | ... | *(+249 more)* |

## Vendor Duplicate Addresses

None — no duplicate addresses in vendor reference.

## Dangerous / Action Registers

These registers require elevated caution: they can reset device state, lock the device, or change communication parameters.

| FC | Address (hex) | Vendor name | Integration name | Access | In integration |
|-----|--------------|-------------|-----------------|--------|----------------|
| FC03 | 0xd | configuration_mode | configuration_mode | RW | yes |
| FC03 | 0xf | access_level | access_level | RW | yes |
| FC03 | 0x113d | hard_reset_settings | hard_reset_settings | RW | yes |
| FC03 | 0x113e | hard_reset_schedule | hard_reset_schedule | RW | yes |
| FC03 | 0x1164 | uart0Id | uart_0_id | RW | yes |
| FC03 | 0x1165 | uart0Baud | uart_0_baud | RW | yes |
| FC03 | 0x1166 | uart0Parity | uart_0_parity | RW | yes |
| FC03 | 0x1167 | uart0Stop | uart_0_stop | RW | yes |
| FC03 | 0x1168 | uart1Id | uart_1_id | RW | yes |
| FC03 | 0x1169 | uart1Baud | uart_1_baud | RW | yes |
| FC03 | 0x116a | uart1Parity | uart_1_parity | RW | yes |
| FC03 | 0x116b | uart1Stop | uart_1_stop | RW | yes |
| FC03 | 0x1fd0 | deviceName | device_name | RW | yes |
| FC03 | 0x1fd1 | deviceName_2 | device_name_2 | RW | yes |
| FC03 | 0x1fd2 | deviceName_3 | device_name_3 | RW | yes |
| FC03 | 0x1fd3 | deviceName_4 | device_name_4 | RW | yes |
| FC03 | 0x1fd4 | deviceName_5 | device_name_5 | RW | yes |
| FC03 | 0x1fd5 | deviceName_6 | device_name_6 | RW | yes |
| FC03 | 0x1fd6 | deviceName_7 | device_name_7 | RW | yes |
| FC03 | 0x1fd7 | deviceName_8 | device_name_8 | RW | yes |
| FC03 | 0x1ffb | lockPass1 | lock_pass | RW | yes |
| FC03 | 0x1ffc | lockPass2 | lock_pass_2 | RW | yes |
| FC03 | 0x1ffd | lockFlag | lock_flag | RW | yes |
| FC03 | 0x1fff | filterChange | filter_change | RW | yes |
