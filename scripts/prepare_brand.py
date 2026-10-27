"""Make size/format derivatives of the selected original brand art; Pillow is development-only."""
from pathlib import Path
from PIL import Image

root=Path('assets/brand')
for name in ('logo','hero'):
    image=Image.open(root/(name+'.png')).convert('RGBA')
    assert image.getextrema()[3][0]==0,'Preserve genuine image alpha'
    # Re-encode without ancillary metadata; the artwork and alpha remain unchanged.
    image.save(root/(name+'.png'))
    sizes=(32,48,64,96) if name=='logo' else (320,480)
    for size in sizes:
        small=image.copy();small.thumbnail((size,size if name=='logo' else int(size*2/3)))
        small.save(root/(name+'-'+str(size)+'.png'))
    if name=='logo':
        canvas=Image.new('RGBA',(256,256));image.thumbnail((244,244))
        canvas.alpha_composite(image,((256-image.width)//2,(256-image.height)//2))
        canvas.save(root/'PartLens.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('Brand PNG variants and Windows icon prepared; alpha preserved.')
