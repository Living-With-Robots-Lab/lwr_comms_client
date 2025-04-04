import asyncio
import websockets
import json
import yaml
import rclpy
from rclpy.node import Node
from rclpy.serialization import serialize_message, deserialize_message
import base64
import threading
import importlib
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

# QoS profile for ROS 2 message reliability
qos_profile = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10
)

ws_connection = None
ws_loop = None
robot_client_instance = None  # Global reference for RobotClient instance

async def ws_client(uri, config):
    """WebSocket client that maintains connection with the server."""
    global ws_connection
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                ws_connection = websocket
                reg_msg = {
                    "robot_name": config.get("robot_name"),
                    "publish_topics": config.get("publish_topics", []),
                    "subscribe_topics": config.get("subscribe_topics", [])
                }
                await websocket.send(json.dumps(reg_msg))
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        print("[Client] Received from server:", data)
                        handle_server_message(data)
                    except websockets.ConnectionClosed:
                        print("WebSocket connection lost, attempting to reconnect...")
                        break
        except Exception as e:
            print(f"WebSocket connection error: {e}, retrying in 5 seconds...")
            await asyncio.sleep(5)

def handle_server_message(data):
    """Processes incoming messages from the WebSocket server."""
    global robot_client_instance
    topic = data.get("topic")
    payload = data.get("data")  # Extract the full payload dictionary

    if topic and payload and topic in robot_client_instance.subscribers:
        encoded_msg = payload.get("data")  # Extract the actual base64 string
        if encoded_msg:
            serialized_msg = base64.b64decode(encoded_msg)
            msg_type = robot_client_instance.subscribers[topic]["msg_type"]
            msg = deserialize_message(serialized_msg, msg_type)
            robot_client_instance.subscribers[topic]["publisher"].publish(msg)

async def send_message_to_server(topic, data):
    """Sends a message to the WebSocket server asynchronously."""
    global ws_connection
    try:
        if ws_connection and ws_connection.state == websockets.protocol.State.OPEN:
            payload = json.dumps({"topic": topic, "data": data})
            await ws_connection.send(payload)
        else:
            print("[Client] WebSocket connection is closed. Reconnecting...")
            await reconnect_websocket()
    except Exception as e:
        print(f"[Client] Failed to send message: {e}")
        await reconnect_websocket()

async def reconnect_websocket():
    global ws_connection
    print("[Client] Reconnecting to WebSocket...")
    try:
        ws_connection = await websockets.connect("ws://10.2.0.60:8080")
        print("[Client] Reconnected successfully.")
    except Exception as e:
        print(f"[Client] Reconnection failed: {e}")
        await asyncio.sleep(5)
        await reconnect_websocket()

def start_ws_client(config):
    """Starts the WebSocket client in a separate event loop."""
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    server_uri = config.get("server_uri", "ws://10.2.0.60:8080")
    ws_loop.run_until_complete(ws_client(server_uri, config))

class RobotClient(Node):
    def __init__(self, config):
        super().__init__('robot_client')
        global robot_client_instance
        robot_client_instance = self  # Assign global instance reference

        self.robot_name = config.get("robot_name")
        self.publish_topics = config.get("publish_topics", [])
        self.subscribe_topics = config.get("subscribe_topics", [])
        self.subscribers = {}  # Instance variable for subscriber management

        self.get_logger().info(f"Robot '{self.robot_name}' started. Publishing: {self.publish_topics}, Subscribing: {self.subscribe_topics}")

        # Set up publishers: subscribe to local ROS topics and forward messages via WebSocket.
        for topic_info in self.publish_topics:
            topic_name = topic_info["name"]
            msg_type = self.get_msg_type(topic_info["type"])
            if msg_type:
                self.create_subscription(msg_type, topic_name, self.get_message_callback(topic_name), qos_profile)
                self.get_logger().info(f"Publishing topic: {topic_name}")

        # Set up subscriptions: receive messages from server and publish them locally.
        for topic_info in self.subscribe_topics:
            topic_name = topic_info["name"]
            msg_type = self.get_msg_type(topic_info["type"])
            if msg_type:
                publisher = self.create_publisher(msg_type, topic_name, qos_profile)
                self.subscribers[topic_name] = {"publisher": publisher, "msg_type": msg_type}
                self.get_logger().info(f"Subscribed to topic: {topic_name}")

    def get_msg_type(self, msg_type_str):
        """Dynamically imports the correct message type."""
        try:
            module_name, class_name = msg_type_str.rsplit(".", 1)
            module = importlib.import_module(module_name)
            return getattr(module, class_name)
        except Exception as e:
            self.get_logger().error(f"Failed to import message type '{msg_type_str}': {e}")
            return None

    def get_message_callback(self, topic):
        """Returns a callback function for publishing messages to WebSocket."""
        def callback(msg):
            serialized = serialize_message(msg)
            encoded_msg = base64.b64encode(serialized).decode('utf-8')
            msg_type = f"{msg.__class__.__module__}.{msg.__class__.__name__}"
            data = {"msg_type": msg_type, "data": encoded_msg}
            # Schedule asynchronous send using the WebSocket event loop
            asyncio.run_coroutine_threadsafe(send_message_to_server(topic, data), ws_loop)
        return callback

def main(args=None):
    with open("/home/bwidemo/bwi_ros2/src/lwr_comms_client/configs/robot_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Start the WebSocket client in a separate thread
    ws_thread = threading.Thread(target=start_ws_client, args=(config,))
    ws_thread.daemon = True
    ws_thread.start()

    rclpy.init(args=args)
    robot_node = RobotClient(config)
    
    try:
        rclpy.spin(robot_node)
    except KeyboardInterrupt:
        pass
    finally:
        robot_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
