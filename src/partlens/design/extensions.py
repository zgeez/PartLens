"""Additive reviewed alternatives; the original patterns remain unchanged for historical replay."""

POWER2='https://www.ti.com/lit/ds/symlink/tps63802.pdf'
TEMP='https://www.ti.com/lit/ds/symlink/tmp117.pdf'

def load_extensions():
    from .patterns import Pattern, Role, cap
    from dataclasses import replace
    class ReviewedPattern(Pattern):
        def evidence(self,field,value):
            return replace(super().evidence(field,value),retrieved_at='2026-10-24')
    return {
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
