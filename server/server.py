import socket
import logging
from os import path
from configs.config import UDP_SERVER_PORT, UDP_SERVER_IP, SERVER_BUFFER_SIZE
from helpers.utils import generate_checksum


class Server:
    def __init__(self) -> None:
        logging.getLogger().setLevel(logging.INFO)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((UDP_SERVER_IP, UDP_SERVER_PORT))
        logging.info(
            f"Server up and listening to {UDP_SERVER_IP} on port {UDP_SERVER_PORT}"
        )

    def receive_request(self) -> dict:
        data, sender_ip = self.server_socket.recvfrom(SERVER_BUFFER_SIZE)
        response = data.decode("utf-8")

        return {"sender_ip": sender_ip, "response": response}

    def parse_response(self, raw_response) -> dict:

        split_header = raw_response["response"].split("/")

        parsed_response = {
            "request_type": split_header[0],
            "file_name": split_header[1],
            "missed_block": split_header[2] if len(split_header) == 3 else None,
        }

        return parsed_response

    def get_blocks_amount(self, file_name) -> int:
        size = path.getsize(filename=file_name)
        blocks_amount = (size // SERVER_BUFFER_SIZE) + 1
        return blocks_amount

    def generate_blocks(self, file_name):
        with open(file_name, "rb") as f:
            while True:
                data = f.read(SERVER_BUFFER_SIZE)
                if not data:
                    break
                yield data

    def generate_payload(self, blocks_amount, file_name) -> list:

        payload = []
        block_index = 1

        for block in self.generate_blocks(file_name):
            check = generate_checksum(block)
            payload.append(
                f"200/{block_index}/{blocks_amount}/{check}/{len(block)}/".encode(
                    "utf-8"
                )
                + block
            )
            block_index += 1

        return payload

    def send_data(self, payload, address) -> None:

        for block in payload:
            self.server_socket.sendto(block, address)

    def run_server(self) -> None:

        while True:
            try:

                raw_response = self.receive_request()

                parsed_response = self.parse_response(raw_response)

                if parsed_response["request_type"] == "retr":
                    file_name = f"request_files/{parsed_response['file_name']}.txt"

                    if path.exists(file_name):
                        blocks_amount = self.get_blocks_amount(file_name=file_name)
                        payload = self.generate_payload(
                            blocks_amount=blocks_amount, file_name=file_name
                        )
                        self.send_data(
                            payload=payload, address=raw_response["sender_ip"]
                        )

                    else:
                        logging.warning(f"File {file_name} was not found in server")
                        self.server_socket.sendto(
                            "404", raw_response["sender_ip"]
                        )  # File not found error code

                elif parsed_response["request_type"] == "fix":

                    file_name = f"request_files/{parsed_response['file_name']}.txt"
                    if path.exists(file_name):
                        blocks_amount = self.get_blocks_amount(file_name=file_name)
                        payload = self.generate_payload(
                            blocks_amount=blocks_amount, file_name=file_name
                        )
                        missed_packet = int(parsed_response["missed_block"])-1
                        fix_payload = [payload[missed_packet]]
                        self.send_data(fix_payload, address=raw_response["sender_ip"])

            except:
                continue
