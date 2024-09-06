from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceServer, RTCConfiguration, RTCIceGatherer
from av import VideoFrame
from PIL import Image
import numpy as np
import argparse
import requests
import asyncio
import cv2
import os
import io
import aioconsole


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="fake")
    parser.add_argument("--url", type=str, required=True, help="server URL")
    parser.add_argument("--cap", type=int, default=0, required=False, help="cap index")
    args = parser.parse_args()

    class CameraVideoTrack(VideoStreamTrack):
        def __init__(self):
            super().__init__()
            self.cap = cv2.VideoCapture(args.cap)
            self.frame_generator = self._frame_generator()

        def _frame_generator(self):
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    continue
                frame = np.array(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                yield VideoFrame.from_ndarray(frame, format="rgb24")

        async def recv(self):
            video_frame = next(self.frame_generator)
            video_frame.pts, video_frame.time_base = await self.next_timestamp()
            return video_frame

    async def main():
        iceServers = [RTCIceServer(urls="stun:stun.l.google.com:19302")]
        pc = RTCPeerConnection(RTCConfiguration(iceServers=iceServers))
        pc.addTrack(CameraVideoTrack())

        @pc.on("track")
        async def on_track(track):
            if track.kind == "video":
                cv2.namedWindow("Received Video", cv2.WINDOW_NORMAL)
                while True:
                    frame = await track.recv()
                    cv2.imshow("Received Video", frame.to_ndarray(format="bgr24"))
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                cv2.destroyAllWindows()

        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            if pc.iceConnectionState == "failed":
                await pc.close()

        await pc.setLocalDescription(await pc.createOffer())
        iceGather = RTCIceGatherer(iceServers=iceServers)
        await iceGather.gather()
        candidates = list(map(lambda x: {"candidate": x.to_sdp(), "sdpMid": "0", "sdpMLineIndex": 0}, iceGather._connection._local_candidates))
        answer = requests.post(args.url, json={'sdp': pc.localDescription.sdp, 'candidates': candidates}).json()
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer['sdp'], type="answer"))

        while True:
            file_name = await aioconsole.ainput("Please enter the source_image file name:\n")
            try:
                if os.path.isfile(file_name):
                    with Image.open(file_name) as img:
                        src = io.BytesIO()
                        img.save(src, format=img.format)
                        res = requests.post(f"{args.url}/src", data=src.getvalue())
                        print(res.json())
                else:
                    print("invalid file name")
            except:
                pass

    asyncio.run(main())
