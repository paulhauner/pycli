import asyncio

from eth2spec.phase0 import spec
from eth2spec.debug.decode import decode
from preset_loader import loader

import websockets
import json
import requests_async as requests

presets = loader.load_presets('eth2.0-specs/configs/', 'minimal')
spec.apply_constants_preset(presets)

BEACON_NODE = "localhost:5052"


# Get a BeaconBlock from a HTTP server.
async def get_block(root):
    key = "0x{}".format(root.hex())
    response = await requests.get(
        "http://{}/beacon/block?root={}".format(BEACON_NODE, key)
    )

    if response.status_code == 200:
        json_state = json.loads(response.text)["beacon_block"]
        return decode(json_state, spec.BeaconBlock)
    else:
        print("Failed to load block: {}".format(key))


# Get a BeaconState from a HTTP server.
async def get_state(root):
    key = "0x{}".format(root.hex())
    response = await requests.get(
        "http://{}/beacon/state?root=0x{}".format(BEACON_NODE, key)
    )

    if response.status_code == 200:
        json_state = json.loads(response.text)["beacon_state"]
        return decode(json_state, spec.BeaconState)
    else:
        print("Failed to load state: {}".format(key))


# Given some block, loads the state of it's parent and performs a
# `state_transition`.
#
# Raises if the state transition failed.
async def process_block(json_block, should_fail):
    print("Processing new block from websocket...")
    block = decode(json_block, spec.BeaconBlock)

    parent_block = await get_block(block.parent_root)

    if parent_block is not None:
        pre_state = await get_state(parent_block.state_root)

        if pre_state is not None:
            try:
                spec.state_transition(pre_state, block)
            except Exception as e:
                if not should_fail:
                    print("WARN: pyspec failed block that client accepted.")
                    print("Exception: {}".format(e))
                else:
                    print("Confirmed block")
            else:
                if should_fail:
                    print("WARN: pyspec did not fail block when client did.")
                else:
                    print("Confirmed block")
        else:
            print("Failed to load state")
    else:
        print("Failed to load block")


# Routes messages to "business logic" functions.
async def message_handler(msg):
    msg = json.loads(msg)

    if msg["event"] == "beacon_block_imported":
        await process_block(msg["data"]["block"], False)
    elif msg["event"] == "beacon_block_rejected":
        await process_block(msg["data"]["block"], True)


# Handles messages from the websocket server, passing them to
# `message_handler`.
async def websocket_handler():
    uri = "ws://localhost:5053"
    async with websockets.connect(uri) as websocket:
        msg = await websocket.recv()
        while msg:
            await message_handler(msg)
            msg = await websocket.recv()

asyncio.get_event_loop().run_until_complete(websocket_handler())
