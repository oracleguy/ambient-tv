

from ambient_tv.models import AppConfig

def write_mdns_file(config: AppConfig, filename):
    """Write a .mdns file with the given channels."""
    with open(filename, "w") as f:
        f.write("<?xml version=\"1.0\" standalone='no'?>\n");
        f.write("<!DOCTYPE service-group SYSTEM \"avahi-service.dtd\">\n");
        f.write("<service-group>\n");
        f.write(f"  <name replace-wildcards=\"yes\">{config.server.name}</name>\n")
        for channel in config.channels:
            f.write(f"  <service>\n")
            f.write(f"    <name replace-wildcards=\"yes\">{channel.name}</name>\n")
            f.write(f"    <type>_rtsp._udp</type>\n")
            f.write(f"    <port>{config.network.rtsp_port}</port>\n")
            f.write(f"    <txt-record>path=/{channel.id}</txt-record>\n")
            f.write(f"  </service>\n")

        f.write("</service-group>\n")