import xml.etree.ElementTree as ET
def add_codec(parent):
  codec = ET.Element("codec")

  # <name>
  name = ET.SubElement(codec, "name")
  name.text = "Apple ProRes 422"

  # <appspecificdata>
  appspecificdata = ET.SubElement(codec, "appspecificdata")

  appname = ET.SubElement(appspecificdata, "appname")
  appname.text = "Final Cut Pro"

  appmanufacturer = ET.SubElement(appspecificdata, "appmanufacturer")
  appmanufacturer.text = "Apple Inc."

  appversion = ET.SubElement(appspecificdata, "appversion")
  appversion.text = "7.0"

  # <data>
  data = ET.SubElement(appspecificdata, "data")

  # <qtcodec>
  qtcodec = ET.SubElement(data, "qtcodec")

  fields = {
      "codecname": "Apple ProRes 422",
      "codectypename": "Apple ProRes 422",
      "codectypecode": "apcn",
      "codecvendorcode": "appl",
      "spatialquality": "1024",
      "temporalquality": "0",
      "keyframerate": "0",
      "datarate": "0"
  }

  for tag, value in fields.items():
      elem = ET.SubElement(qtcodec, tag)
      elem.text = value

  # Xuất XML ra string
  ET.tostring(codec, encoding="utf-8").decode("utf-8")

def add_rate(parent, fps, ntsc):
   rate = ET.SubElement(parent, 'rate')
   ET.SubElement(rate, 'timebase').text = str(fps)
   ET.SubElement(rate, 'ntsc').text = str(ntsc)

def add_audio_source_track(parent, track_index):
    source_track = ET.SubElement(parent, 'sourcetrack')
    ET.SubElement(source_track, 'mediatype').text = 'audio'
    ET.SubElement(source_track, 'trackindex').text = str(track_index)

def add_marker(parent):
    marker_data = [
        {"in": "9", "out": "-1"},
        {"in": "9", "out": "-1"},
        {"in": "6", "out": "-1"}]

    for m in marker_data:
        marker = ET.SubElement(parent, "marker")
        ET.SubElement(marker, "comment").text = ""
        ET.SubElement(marker, "name").text = ""
        ET.SubElement(marker, "in").text = m["in"]
        ET.SubElement(marker, "out").text = m["out"]