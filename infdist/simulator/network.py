from collections import defaultdict
import json

import ns.applications
import ns.core
import ns.internet
import ns.network
import ns.mobility
import ns.point_to_point
import ns.wifi

from . import simulator
from optimization.models import Message
from optimization.network import BaseNetwork


class DataTypesStore:
    def __init__(self):
        self.data_types = {}
        self.hashes = {}

    def get_hash(self, data_type_name):
        if data_type_name not in self.data_types:
            h = bytes([len(self.data_types)])
            self.data_types[data_type_name] = h
            self.hashes[h] = data_type_name
        return self.data_types[data_type_name]

    def get_data_type_name(self, h):
        return self.hashes[h]


class NS3Network(BaseNetwork):
    DATA_PORT = 4477
    BACKGROUND_PORT = 8082
    AVAILABLE_DATA_RATES = {
        1: 'DsssRate1Mbps',
        2: 'DsssRate2Mbps',
        5.5: 'DsssRate5_5Mbps',
        11: 'DsssRate11Mbps',
    }

    def __init__(self, nodes_num, data_rate=5.5):
        self.initialized = False
        self.known_data_types = DataTypesStore()
        self._message_received_callbacks = defaultdict(set)

        self.nodes = ns.network.NodeContainer()
        self.nodes.Create(nodes_num)
        self.set_data_rate(data_rate)
        self.background_noise_mode = 'tcp'
        self.background_noise_history = []

        self._init_network()

        self.sockets = [
            ns.network.Socket.CreateSocket(
                self.nodes.Get(i),
                ns.core.TypeId.LookupByName("ns3::UdpSocketFactory")
            )
            for i in range(nodes_num)
        ]

        any_address = ns.network.InetSocketAddress(
            ns.network.Ipv4Address.GetAny(), self.DATA_PORT
        )
        broadcast_address = ns.network.InetSocketAddress(
            ns.network.Ipv4Address.GetBroadcast(), self.DATA_PORT
        )
        for i, socket in enumerate(self.sockets):
            socket.SetRecvCallback(self._gen_ns3_receive_callback(i))
            socket.SetAllowBroadcast(True)
            socket.Bind(any_address)
            socket.Connect(broadcast_address)

    def serialize(self, native_message):
        return native_message

    def deserialize(self, message):
        return message

    def add_background_traffic_pattern(
        self,
        background_traffic_pattern,
        mode='tcp',
    ):
        for t_start, t_end, throughput in zip(
            background_traffic_pattern.ts[:-1],
            background_traffic_pattern.ts[1:],
            background_traffic_pattern.throughputs
        ):
            self.add_background_traffic(t_start, t_end, throughput, mode)

    def add_background_traffic(self, t_start, t_end, throughput, mode='tcp'):
        """
        throughput in Mbps
        """
        assert mode in ('tcp', 'udp')
        self.background_noise_mode = mode
        any_address = ns.network.InetSocketAddress(
            ns.network.Ipv4Address.GetAny(), self.BACKGROUND_PORT
        )

        def source_rcvd(socket):
            packet = socket.Recv(2048, 0)
            self.background_noise_history.append(
                (simulator.now_float(), packet.GetSize())
            )

        def succeeded(a):
            # print("Connected")
            pass

        def not_succeeded(a):
            print("ERROR: not connected")

        def accept_callback(a, b):
            return True

        def new_connection(socket, address):
            socket.SetRecvCallback(source_rcvd)

        sockets = []
        for i in range(1, 3):
            node = self.nodes.Get(i)
            socket = ns.network.Socket.CreateSocket(
                node,
                ns.core.TypeId.LookupByName(
                    "ns3::TcpSocketFactory"
                    if self.background_noise_mode == 'tcp' else
                    "ns3::UdpSocketFactory"
                )
            )
            socket.Bind(any_address)
            socket.Listen()
            sockets.append(socket)

            if self.background_noise_mode != 'tcp':
                socket.SetRecvCallback(source_rcvd)

            socket.SetConnectCallback(succeeded, not_succeeded)
            socket.SetAcceptCallback(accept_callback, new_connection)

        self.reinit_background_source()
        self.background_packet_size = 2048
        packets = int(
            throughput*10**6/8*(t_end-t_start)/self.background_packet_size
        )
        for i in range(packets):
            simulator.schedule(
                t_start + i/packets * (t_end-t_start),
                self.send_background_packet
            )

    def reinit_background_source(self):
        def send_callback(a, b):
            pass

        def succeeded(a):
            # print("Connected")
            pass

        def not_succeeded(a):
            print("ERROR: not connected")

        source = ns.network.Socket.CreateSocket(
            self.nodes.Get(0),
            ns.core.TypeId.LookupByName(
                "ns3::TcpSocketFactory"
                if self.background_noise_mode == 'tcp' else
                "ns3::UdpSocketFactory"
            )
        )
        source.SetConnectCallback(succeeded, not_succeeded)
        source.SetSendCallback(send_callback)

        self.background_source = source
        self.connect_background()

    def send_background_packet(self, size=None):
        if size is None:
            size = self.background_packet_size
        if(self.background_source.GetTxAvailable() < size):
            self.reinit_background_source()
            return
        packet = ns.network.Packet(size)
        self.background_source.Send(packet, 0)
        # print(self.background_source.GetErrno())

    def connect_background(self):
        sink_address = ns.network.InetSocketAddress(
            ns.network.Ipv4Address("10.1.1.2"), self.BACKGROUND_PORT,
        )
        self.background_source.Connect(sink_address)

    def set_data_rate(self, data_rate):
        assert not self.initialized, \
            "Cannot change data rate after network initialization"
        assert data_rate in self.AVAILABLE_DATA_RATES, "Unsupported data rate"
        self.phy_mode = self.AVAILABLE_DATA_RATES[data_rate]

    def _init_network(self):
        self.initialized = True
        rss = -80

        wifi = ns.wifi.WifiHelper()
        wifi.SetStandard(ns.wifi.WIFI_PHY_STANDARD_80211g)

        wifi_phy = ns.wifi.YansWifiPhyHelper.Default()
        wifi_phy.Set("RxGain", ns.core.DoubleValue(0))
        wifi_phy.SetPcapDataLinkType(
            ns.wifi.YansWifiPhyHelper.DLT_IEEE802_11_RADIO
        )

        wifi_channel = ns.wifi.YansWifiChannelHelper()
        wifi_channel.SetPropagationDelay(
            "ns3::ConstantSpeedPropagationDelayModel"
        )
        # fixed RSS regardless of the distance and transmit power
        wifi_channel.AddPropagationLoss(
            "ns3::FixedRssLossModel",
            "Rss",
            ns.core.DoubleValue(rss)
        )

        wifi_phy.SetChannel(wifi_channel.Create())

        # disable rate control
        wifi.SetRemoteStationManager(
            "ns3::ConstantRateWifiManager",
            "DataMode", ns.core.StringValue(self.phy_mode),
            "ControlMode", ns.core.StringValue(self.phy_mode),
        )

        wifi_mac = ns.wifi.WifiMacHelper()
        wifi_mac.SetType("ns3::AdhocWifiMac")

        # mobility
        mobility = ns.mobility.MobilityHelper()
        positions = ns.mobility.ListPositionAllocator()
        for i in range(self.nodes.GetN()):
            positions.Add(ns.mobility.Vector(5*i, int(i/5)*2, 0))

        mobility.SetPositionAllocator(positions)
        mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel")
        mobility.Install(self.nodes)

        devices = wifi.Install(wifi_phy, wifi_mac, self.nodes)

        self._init_ip(devices)

    def _init_ip(self, devices):
        stack = ns.internet.InternetStackHelper()
        stack.Install(self.nodes)

        address = ns.internet.Ipv4AddressHelper()
        address.SetBase(ns.network.Ipv4Address("10.1.1.0"),
                        ns.network.Ipv4Mask("255.255.255.0"))

        address.Assign(devices)

    def add_message_received_callback(self, callback, node_id):
        self._message_received_callbacks[node_id].add(callback)

    def _message_received(self, message, node_id):
        for callback in self._message_received_callbacks[node_id]:
            callback(message)

    def _header2message(self, header, receivers, size):
        t_gen = header.GetTimestamp()/10**9
        return Message(
            header.GetSender(),
            receivers=receivers,
            t_sent=t_gen,
            data_type_name=self.known_data_types.get_data_type_name(
                header.GetDataType()),
            size=size,
            data=json.loads(header.GetData()),
            t_gen=t_gen,
            t_rcv=simulator.now_float(),
        )

    def _gen_ns3_receive_callback(self, node_id):
        def _ns3_receive_callback(socket):
            packet = socket.Recv()
            header = ns.network.InfDistHeader()
            packet.RemoveHeader(header)
            # print("rcvd", self._header_repr(header), ns.core.Simulator.Now())
            self._message_received(
                self._header2message(header, {node_id}, packet.GetSize()),
                node_id,
            )
        return _ns3_receive_callback

    @staticmethod
    def _header_repr(header):
        return '{}@{} from {}; data="{}"'.format(
            header.GetDataType(),
            header.GetTimestamp(),
            header.GetSender(),
            header.GetData(),
        )

    def send(self, message):
        packet = ns.network.Packet(message.size)

        header = ns.network.InfDistHeader()
        header.SetDataType(
            self.known_data_types.get_hash(message.data_type_name)
        )
        header.SetTimestamp(simulator.now())
        header.SetSender(message.sender)
        data = json.dumps(vars(message.data))
        header.SetData(len(data), data)
        packet.AddHeader(header)
        self.sockets[message.sender].Send(packet)
