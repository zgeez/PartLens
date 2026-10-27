"""Additive reviewed alternatives; the original patterns remain unchanged for historical replay."""

POWER2='https://www.ti.com/lit/ds/symlink/tps63802.pdf'
TEMP='https://www.ti.com/lit/ds/symlink/tmp117.pdf'
XC6206='https://product.torexsemi.com/system/files/series/xc6206.pdf'
USB_C='https://www.usb.org/document-library/usb-type-cr-cable-and-connector-specification-revision-23'
JST_SH='https://www.jst-mfg.com/product/pdf/eng/eSH.pdf'
LED_REF='https://www.lcsc.com/product-detail/C434448.html'


def load_extensions(features=()):
    from .patterns import Pattern, Role, cap
    from dataclasses import replace
    class ReviewedPattern(Pattern):
        def evidence(self,field,value):
            return replace(super().evidence(field,value),retrieved_at='2026-10-24')
    base={
        'power.tps63802':ReviewedPattern('power.tps63802','power','Adjustable buck-boost, proposed 3.3 V reference',
            POWER2,'page=17',(
                Role('converter','U',1,'ic','3.3V buck-boost','VSON-10(2x3)','Texas Instruments','TPS63802DLAR',('C2845237',),
                     nets=('VBAT','3V3','GND','SW1','SW2','FB')),
                Role('inductor','L',1,'inductor','0.47uH','','Coilcraft','XFL4015-471ME',
                     nets=('SW1','SW2'),omissions=('exact orderable suffix, load-derived saturation margin, thermal and layout review required',)),
                cap('input_bulk','10uF',codes=('C19702',),nets=('VBAT','GND')),
                Role('output_bulk','C',1,'capacitor','22uF',parameters=(('capacitance','22uF'),),nets=('3V3','GND'),
                     omissions=('effective output capacitance, bias, ESR and exact part unresolved',)),
                Role('feedback_upper','R',1,'resistor','511k','0603',parameters=(('resistance','511k'),),nets=('3V3','FB')),
                Role('feedback_lower','R',1,'resistor','91k','0603',parameters=(('resistance','91k'),),nets=('FB','GND')),
                Role('power_good_pullup','R',1,'resistor','100k','0603',parameters=(('resistance','100k'),),nets=('3V3','PG')),
            ),omissions=('2 A capability conditional on Vin >=2.3 V, Vout=3.3 V; startup >1.8 V',
                         'feedback tolerances, capacitor derating, transient/thermal/efficiency and exact connections unresolved')),
        'temperature.tmp117':ReviewedPattern('temperature.tmp117','temperature','Digital temperature measurement over I2C',
            TEMP,'page=35',(
                Role('sensor','U',1,'ic','digital temperature sensor','WSON-6(2x2)','Texas Instruments','TMP117MAIDRVR',('C2803242',),
                     nets=('3V3','GND','I2C_SDA','I2C_SCL','TEMP_ALERT','TEMP_ADD0')),
                cap('local_bypass','100nF',codes=('C1525',)),
                Role('i2c_sda_pullup','R',1,'resistor','I2C pull-up resistance: calculate from bus capacitance and sink limits',
                     nets=('3V3','I2C_SDA'),omissions=('capacitance/rise-time and sink limits unresolved',)),
                Role('i2c_scl_pullup','R',1,'resistor','I2C pull-up resistance: calculate from bus capacitance and sink limits',
                     nets=('3V3','I2C_SCL'),omissions=('capacitance/rise-time and sink limits unresolved',)),
            ),('1.8','5.5'),'i2c',None,('ADD0 ground proposes 0x48, but strap/net connectivity must be verified',
                                               'temperature accuracy depends on mounting, self-heating and application conditions')),
    }
    if 'breadboard_power' in features:
        base.update({
            'power.xc6206_ldo':ReviewedPattern('power.xc6206_ldo','power','3.3 V 250 mA CMOS LDO linear regulator reference',
                XC6206,'page=2',(
                    Role('regulator','U',1,'ic','3.3V 250mA LDO','SOT-23','UMW','XC6206P332MR',('C347376',),
                         (('output_voltage','3.3V'),('output_current','250mA')),('VIN','3V3','GND'),
                         ('Torex XC6206 datasheet specifies 1.8..6.0 V recommended operating input whereas LCSC C347376 lists 8 V; SOT-23 250 mW thermal limit restricts continuous load current',),
                         XC6206),
                    cap('input_bypass','1uF',nets=('VIN','GND')),
                    cap('output_bypass','1uF',nets=('3V3','GND')),
                ),omissions=('250 mA current limit and 250 mW SOT-23 thermal ceiling restrict continuous breadboard loads',
                             'Torex datasheet recommended Vin max is 6.0 V; supplier 8 V field is not manufacturer operating rating')),
            'input_power.usb_c_5v':ReviewedPattern('input_power.usb_c_5v','input_power',
                'USB-C 5 V DC input with 5.1k CC sink pulldowns, Schottky reverse-polarity diode and control switch',
                USB_C,'section=4.5',(
                    Role('usb_connector','J',1,'connector','USB-C 16P 5V input receptacle','SMD','SHOU HAN','TYPE-C 16PIN 2MD(073)',
                         ('C2765186',),(('voltage_rating','5V'),('temp_range','-25~85')),('VBUS_IN','USB_CC1','USB_CC2','GND'),
                         ('shell grounding, ESD protection and mechanical retention unverified',),'https://www.lcsc.com/product-detail/C2765186.html'),
                    Role('cc_pulldown','R',2,'resistor','5.1k','0402','UNI-ROYAL','0402WGF5101TCE',('C25905',),
                         (('resistance','5.1k'),('tolerance_pct','1%'),('power_w','62.5mW'),('temp_range','-55~155')),
                         ('USB_CC1','USB_CC2','GND'),('independent CC1 and CC2 pulldown termination required for 5 V sink detection',),
                         'https://www.lcsc.com/product-detail/C25905.html'),
                    Role('protection_diode','D',1,'diode','40V 1A Schottky reverse-polarity diode','SOD-123','JSCJ','B5819W SL',
                         ('C8598',),(),('VBUS_IN','VIN'),
                         ('forward voltage drop (~0.45..0.60 V at load) reduces pass-through 5 V rail voltage',),
                         'https://www.lcsc.com/product-detail/C8598.html'),
                    Role('power_switch','SW',1,'switch','SPST tactile control switch','SMD-4P,4.2x3.2mm','ALPSALPINE','SKRPACE010',
                         ('C139797',),(('voltage_rating','16V'),('temp_range','-30~85')),('VIN','EN'),
                         ('50 mA switch contact rating supports enable control only, not direct 500 mA power-path switching',),
                         'https://www.lcsc.com/product-detail/C139797.html'),
                    cap('input_decoupling','10uF',codes=('C19702',),nets=('VIN','GND')),
                ),omissions=('USB-C VBUS hot-plug capacitance limit (<=10 uF effective) and overcurrent polyfuse not yet included',
                             'Schottky diode drop reduces pass-through 5 V rail voltage under load')),
            'rail_output.breadboard_headers':ReviewedPattern('rail_output.breadboard_headers','rail_output',
                'Dual breadboard power rail output headers with high-frequency decoupling and auxiliary 3P tap',
                JST_SH,'page=1',(
                    cap('rail_decoupling','100nF',2,codes=('C1525',),nets=('3V3','VIN','GND')),
                    Role('auxiliary_header','J',1,'connector','3P 1mm auxiliary rail tap','SMD,P=1mm','JST','BM03B-SRSS-TB(LF)(SN)',
                         ('C160389',),(('current_rating','1A'),('temp_range','-25~85')),('VIN','3V3','GND'),
                         ('wire harness mating connector and pinout polarization unverified',),JST_SH),
                    Role('breadboard_rail_headers','J',2,'connector','2x2P 2.54mm through-hole breadboard rail headers: unresolved',
                         'P=2.54mm','','',(),(),('VIN','3V3','GND'),
                         ('exact through-hole header MPN, MB-102 rail span pitch and mechanical insertion retention unresolved',)),
                    Role('rail_selector_header','J',2,'connector','1x3P 2.54mm rail voltage selector jumper header',
                         '插件,P=2.54mm','BOOMELE(Boom Precision Elec)','2.54-1*3P针',('C49257',),(),('VIN','3V3','RAIL_A','RAIL_B'),
                         ('shunt jumper current rating and mechanical clearance unresolved',
                          '2.54 mm shunt jumper caps are not a BOM line yet'),
                         'https://www.lcsc.com/product-detail/C49257.html'),
                ),omissions=('physical pin spacing between left and right breadboard power strips requires mechanical CAD verification',)),
            'indicator.power_led':ReviewedPattern('indicator.power_led','indicator',
                '3.3 V rail power-good LED indicator with current-limiting resistor',
                LED_REF,'spec',(
                    Role('status_led','LED',1,'led','White 0402 status LED','0402','Yongyu Photoelectric','SZYY0402W',
                         ('C434448',),(('temp_range','-40~85'),),('3V3','LED_K'),
                         ('forward voltage tolerance (2.8 V nominal) and luminous intensity at ~0.5 mA unverified',),LED_REF),
                    Role('led_resistor','R',1,'resistor','1k','0402','UNI-ROYAL','0402WGF1001TCE',('C11702',),
                         (('resistance','1k'),('tolerance_pct','1%'),('power_w','62.5mW'),('temp_range','-55~155')),
                         ('LED_K','GND'),(),'https://www.lcsc.com/product-detail/C11702.html'),
                ),('3.0','5.5'),omissions=('LED current is derived from nominal 3.3 V rail and 2.8 V Vf; optical brightness is unverified',)),
        })
    return base
