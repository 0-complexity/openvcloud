from xml.etree import ElementTree
from jinja2 import Environment, FunctionLoader
import os
from StringIO import StringIO

SIZES = {
    "gigabytes": 1024 * 1024 * 1024,
    "megabytes": 1024 * 1024,
    "kilobytes": 1024,
    "bytes": 1,
    "byte * 2^20": 2 ** 20,
    "byte * 2^30": 2 ** 30,
}


def _get_namespaces(xml):
    return dict(
        [node for _, node in ElementTree.iterparse(StringIO(xml), events=["start-ns"])]
    )


def _findsubitem(obj, itemname):
    """Finds item in object if itemname is obj.tag
    Mainly to neglect searching with namespaces
    """
    return [x for x in obj.getchildren() if itemname in x.tag][0]


def ovf_to_model(ovf):
    namespaces = _get_namespaces(ovf)
    namespaces.pop("")
    envelope = ElementTree.fromstring(ovf)
    files = dict(
        (file.get("{%(ovf)s}id" % namespaces), file.get("{%(ovf)s}href" % namespaces))
        for file in envelope.findall("ovf:References/ovf:File", namespaces)
    )
    disksobjs = (
        ds.find("ovf:Disk", namespaces)
        for ds in envelope.findall("ovf:DiskSection", namespaces)
    )
    disks = {}
    for obj in disksobjs:
        units = obj.get("{%(ovf)s}capacityAllocationUnits" % namespaces)
        size = int(obj.get("{%(ovf)s}capacity" % namespaces))
        if units:
            size = size * SIZES[units]

        disks[obj.get("{%(ovf)s}diskId" % namespaces)] = {
            "size": size,
            "name": obj.get("{%(ovf)s}diskId" % namespaces),
            "file": files[obj.get("{%(ovf)s}fileRef" % namespaces)],
        }
    hw = envelope.find("ovf:VirtualSystem/ovf:VirtualHardwareSection", namespaces)
    itemobjs = hw.findall("ovf:Item", namespaces)
    itemobjsdict = {}
    for item in itemobjs:
        addressnode = item.find("rasd:Address", namespaces)
        address = addressnode.text if addressnode is not None else None
        instanceid = _findsubitem(item, "InstanceID").text
        resourcetype = _findsubitem(item, "ResourceType").text
        itemobjsdict[instanceid] = (address, resourcetype)

    storageitemobjs = hw.findall("ovf:StorageItem", namespaces)

    def get_disk_items(disktype, objects):
        diskobjects = []
        for storage in objects:
            if (
                storage.find("{}:ResourceType".format(disktype), namespaces).text
                == "17"
            ):
                parent = itemobjsdict[
                    storage.find("{}:Parent".format(disktype), namespaces).text
                ][0]
                parentaddress = storage.find(
                    "{}:AddressOnParent".format(disktype), namespaces
                ).text
                disk = disks[
                    storage.find(
                        "{}:HostResource".format(disktype), namespaces
                    ).text.split("/")[-1]
                ]
                diskobjects.append(((parent, parentaddress), disk))
        diskobjects.sort()
        return map(lambda x: x[1], diskobjects)

    if storageitemobjs:
        diskitems = get_disk_items("sasd", storageitemobjs)
    else:
        diskitems = get_disk_items("rasd", itemobjs)

    namesection = envelope.find("ovf:VirtualSystem/ovf:Name", namespaces)
    name = namesection.text if namesection is not None else ""
    infosection = envelope.find("ovf:VirtualSystem/ovf:Info", namespaces)
    description = infosection.text if infosection is not None else ""

    cpus = [
        int(_findsubitem(i, "VirtualQuantity").text)
        for i in itemobjs
        if _findsubitem(i, "ResourceType").text == "3"
    ][0]
    mem = [
        int(_findsubitem(i, "VirtualQuantity").text)
        * SIZES[_findsubitem(i, "AllocationUnits").text.lower()]
        for i in itemobjs
        if _findsubitem(i, "ResourceType").text == "4"
    ][0]
    raw = True
    for disk in diskitems:
        if os.path.splitext(disk["file"])[1] != ".raw":
            raw = False
            break
    return {
        "name": name,
        "description": description,
        "cpus": cpus,
        "mem": mem,
        "raw": raw,
        "disks": diskitems,
    }


def template(name):
    return """<?xml version="1.0"?>
<Envelope ovf:version="2.0" xml:lang="en-US"
 xmlns="http://schemas.dmtf.org/ovf/envelope/2"
 xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/2"
 xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData.xsd"
 xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData.xsd"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:epasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_EthernetPortAllocationSettingData.xsd"
 xmlns:sasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_StorageAllocationSettingData.xsd">
  {% for disk in disks %}
  <References>
    <File ovf:href="{{disk.name}}" ovf:id="file{{loop.index0}}"/>
  </References>
  {% endfor %}
  {% for disk in disks %}
  <DiskSection>
    <Info>List of the virtual disks used in the package</Info>
    <Disk ovf:capacity="{{disk.size}}" ovf:diskId="vmdisk{{loop.index0}}" ovf:fileRef="file{{loop.index0}}"
     ovf:format="http://www.vmware.com/specifications/raw.html"/>
  </DiskSection>
  {% endfor %}
  <NetworkSection>
    <Info>Logical networks used in the package</Info>
    <Network ovf:name="NAT">
      <Description>Logical network used by this appliance.</Description>
    </Network>
  </NetworkSection>
  <VirtualSystem ovf:id="{{os}}">
    <Name>{{name}}</Name>
    <Info>{{description}}</Info>
    <OperatingSystemSection ovf:id="94">
      <Info>The kind of installed guest operating system</Info>
      <Description>{{osname}}</Description>
    </OperatingSystemSection>
    <VirtualHardwareSection>
      <Info>Virtual hardware requirements for a virtual machine</Info>
      <System>
        <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
        <vssd:InstanceID>0</vssd:InstanceID>
        <vssd:VirtualSystemIdentifier>{{os}}</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>kvm</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:Caption>1 virtual CPU</rasd:Caption>
        <rasd:Description>Number of virtual CPUs</rasd:Description>
        <rasd:InstanceID>1</rasd:InstanceID>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>{{cpus}}</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:AllocationUnits>MegaBytes</rasd:AllocationUnits>
        <rasd:Caption>512 MB of memory</rasd:Caption>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:InstanceID>2</rasd:InstanceID>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:VirtualQuantity>{{mem}}</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Address>0</rasd:Address>
        <rasd:Caption>ideController0</rasd:Caption>
        <rasd:Description>IDE Controller</rasd:Description>
        <rasd:InstanceID>3</rasd:InstanceID>
        <rasd:ResourceSubType>PIIX4</rasd:ResourceSubType>
        <rasd:ResourceType>5</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:Address>1</rasd:Address>
        <rasd:Caption>ideController1</rasd:Caption>
        <rasd:Description>IDE Controller</rasd:Description>
        <rasd:InstanceID>4</rasd:InstanceID>7
        <rasd:ResourceSubType>PIIX4</rasd:ResourceSubType>
        <rasd:ResourceType>5</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:Address>0</rasd:Address>
        <rasd:Caption>sataController0</rasd:Caption>
        <rasd:Description>SATA Controller</rasd:Description>
        <rasd:InstanceID>5</rasd:InstanceID>
        <rasd:ResourceSubType>AHCI</rasd:ResourceSubType>
        <rasd:ResourceType>20</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:Address>0</rasd:Address>
        <rasd:Caption>usb</rasd:Caption>
        <rasd:Description>USB Controller</rasd:Description>
        <rasd:InstanceID>6</rasd:InstanceID>
        <rasd:ResourceType>23</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AddressOnParent>3</rasd:AddressOnParent>
        <rasd:AutomaticAllocation>false</rasd:AutomaticAllocation>
        <rasd:Caption>sound</rasd:Caption>
        <rasd:Description>Sound Card</rasd:Description>
        <rasd:InstanceID>7</rasd:InstanceID>
        <rasd:ResourceSubType>ensoniq1371</rasd:ResourceSubType>
        <rasd:ResourceType>35</rasd:ResourceType>
      </Item>
      <EthernetPortItem>
        <epasd:AutomaticAllocation>true</epasd:AutomaticAllocation>
        <epasd:Caption>Ethernet adapter on 'NAT'</epasd:Caption>
        <epasd:Connection>NAT</epasd:Connection>
        <epasd:InstanceID>10</epasd:InstanceID>
        <epasd:ResourceSubType>E1000</epasd:ResourceSubType>
        <epasd:ResourceType>10</epasd:ResourceType>
      </EthernetPortItem>
      {% for disk in disks %}
      <StorageItem>
        <sasd:AddressOnParent>{{loop.index0}}</sasd:AddressOnParent>
        <sasd:Caption>disk1</sasd:Caption>
        <sasd:Description>Disk Image</sasd:Description>
        <sasd:HostResource>/disk/vmdisk{{loop.index0}}</sasd:HostResource>
        <sasd:InstanceID>{{9 + loop.index0}}</sasd:InstanceID>
        <sasd:Parent>5</sasd:Parent>
        <sasd:ResourceType>17</sasd:ResourceType>
      </StorageItem>
      {% endfor %}
    </VirtualHardwareSection>
  </VirtualSystem>
</Envelope>"""


def model_to_ovf(model):
    env = Environment(loader=FunctionLoader(template))
    return env.get_template("").render(model)


if __name__ == "__main__":
    print(
        ovf_to_model(
            model_to_ovf(
                {
                    "name": "vm",
                    "description": "vm-desc",
                    "cpus": 1,
                    "mem": 1024,
                    "os": "ubuntu",
                    "osname": "Ubuntu 64",
                    "disks": [
                        {"name": "vm0.vmdk", "size": "1023123"},
                        {"name": "vm1.vmdk", "size": "222222"},
                    ],
                }
            )
        )
    )
