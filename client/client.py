import socket
import logging
from random import randint

from configs.config import (
    UDP_CLIENT_PORT,
    UDP_CLIENT_IP,
    CLIENT_BUFFER_SIZE,
    DEFAULT_CLIENT_REQUEST,
)
from helpers.utils import verify_checksum


class Client:
    def __init__(self) -> None:
        logging.getLogger().setLevel(logging.INFO)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.settimeout(10)
        logging.info(
            f"client up and ready from {UDP_CLIENT_IP} on port {UDP_CLIENT_PORT}"
        )

    def generate_request(self, request_type, file_name) -> str:

        payload = (f"{request_type}/{file_name}").encode("utf-8")
        return payload

    def send_request(self, payload) -> None:

        self.client_socket.sendto(payload, (UDP_CLIENT_IP, UDP_CLIENT_PORT))

    def startup_selections(self) -> dict:
        logging.info(
            """Select desired file size for request by choosing one of the following numbers
    small_payload: 1,
    medium_payload: 2,
    large_payload: 3,
    cancel: 0""",
        )
        file_option = input()

        match file_option:
            case "1":
                file_name = "small_payload"
            case "2":
                file_name = "medium_payload"
            case "3":
                file_name = "large_payload"
            case _:
                file_name = None

        logging.info(
            """Select data integrity simulation:
    full_data: 0, 
    broken_data: 1"""
        )
        integrity = input()

        return {"file_name": file_name, "integrity": integrity}

    def await_data(self) -> list:
        data, address = self.client_socket.recvfrom(CLIENT_BUFFER_SIZE)
        decoded_data = data.decode("utf-8")
        split_data = decoded_data.split("/")
        split_data[5] = split_data[5].encode("utf-8")

        return split_data

    def check_received_blocks(self, received_blocks, total_blocks) -> bool:
        return len(received_blocks) == total_blocks

    def rebuild_data(self, received_blocks, file_name) -> None:
        with open(f"received_files/{file_name}.txt", "wb") as file:
            for block_index in range(1, len(received_blocks) + 1):
                file.write(received_blocks[block_index])

    def check_missing(self, received_blocks, total_blocks) -> list:
        if len(received_blocks) < total_blocks:
            missing_blocks = [
                block_index
                for block_index in range(1, total_blocks + 1)
                if block_index not in received_blocks
            ]
            return missing_blocks
        else:
            return []

    def run_client(self) -> None:

        user_input = self.startup_selections()

        if not user_input['file_name']:
            logging.info("Client execution canceled. Aborting.")
        else:

            payload = self.generate_request(
                request_type=DEFAULT_CLIENT_REQUEST, file_name=user_input["file_name"]
            )

            self.send_request(payload=payload)

            received_blocks = {}

            lost_block = -1

            block_dropped = False

            missing_blocks = []

            while True:
                try:
                    split_data = self.await_data()

                    if split_data[0] == "200":

                        current_block = int(split_data[1])
                        total_blocks = int(split_data[2])
                        check = split_data[3]

                        if user_input["integrity"] == "1" and lost_block == -1:
                            lost_block = randint(1, total_blocks)
                            

                        if verify_checksum(split_data[5], check):
                            received_blocks[current_block] = split_data[5]
                            if (
                                user_input["integrity"] == "1"
                                and current_block == lost_block
                                and not block_dropped
                            ):
                                logging.warning(
                                    f"Dropping block {current_block} for testing"
                                )
                                received_blocks.pop(current_block)
                                block_dropped = True
                        else:
                            logging.warning(
                                f"Checksum verfication failed on block {current_block}. Requesting lost packet"
                            )
                            self.client_socket.sendto(
                                f"fix/{user_input['file_name']}/{current_block}".encode(
                                    "utf-8"
                                ),
                                (UDP_CLIENT_IP, UDP_CLIENT_PORT),
                            )

                        print(f"checking block {current_block}")
                        if self.check_received_blocks(
                            received_blocks=received_blocks, total_blocks=total_blocks
                        ):
                            logging.info("Rebuilding data")
                            self.rebuild_data(
                                received_blocks=received_blocks,
                                file_name=user_input["file_name"],
                            )
                            logging.info(
                                f'File data received and materialized at received_files/{user_input["file_name"]}.txt'
                            )

                    else:
                        match split_data[0]:
                            case "404":
                                logging.error("File not found")
                            case _:
                                logging.error("Client error")
                        break

                except socket.timeout:
                    if not split_data:
                        self.send_request(payload=payload)

                    missing_blocks = self.check_missing(received_blocks, total_blocks)

                    if missing_blocks == []:
                        logging.info("All blocks received")
                        break

                    else:
                        for block in missing_blocks:
                            self.client_socket.sendto(
                                f"fix/{user_input['file_name']}/{block}".encode("utf-8"),
                                (UDP_CLIENT_IP, UDP_CLIENT_PORT),
                            )

                except ConnectionResetError:
                    self.send_request(payload=payload)
                    continue
