"""Resolution-independent boss region and safe screenshot cropping."""
def general_region(monitor):
    return {'left':monitor['left']+round(monitor['width']*.25),
            'top':monitor['top']+round(monitor['height']*.10),
            'width':round(monitor['width']*.75)-round(monitor['width']*.25),
            'height':round(monitor['height']*.16)-round(monitor['height']*.10)}


def crop_region(image, region, monitor):
    sx,sy=image.shape[1]/monitor['width'],image.shape[0]/monitor['height']
    x=round((region['left']-monitor['left'])*sx)
    y=round((region['top']-monitor['top'])*sy)
    right=round((region['left']-monitor['left']+region['width'])*sx)
    bottom=round((region['top']-monitor['top']+region['height'])*sy)
    return image[max(0,y):max(0,min(image.shape[0],bottom)),max(0,x):max(0,min(image.shape[1],right)),:3]


def lookup_description(details):
    if not details:
        return 'Boss lookup: no diagnostics recorded for this older death'
    state=details.get('status','pending')
    if state=='confirmed':
        return f"Boss confirmed in {details['source']}: {details['boss']}"
    if state=='pending':
        return 'Boss lookup pending…'
    return 'Boss UNCONFIRMED — '+details.get('reason','no repeated name found')
