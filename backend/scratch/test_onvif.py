import asyncio
import sys
sys.path.insert(0, r'e:\VMS\backend')

from services.onvif_service import ONVIFService

async def main():
    svc = ONVIFService()
    cam = await svc.connect_camera('192.168.4.243', 'admin', 'Admin@123', port=80)
    if cam:
        print('SUCCESS: Connected to camera!')
        print('cam.devicemgmt:', cam.devicemgmt)
        
        # Test getting profiles
        try:
            profiles = await svc.get_video_profiles('192.168.4.243', 'admin', 'Admin@123', port=80)
            print(f'Got {len(profiles)} video profiles:')
            for p in profiles:
                print(f'  {p["name"]}: {p["resolution"]["width"]}x{p["resolution"]["height"]} @ {p["frame_rate"]}fps')
        except Exception as e:
            print(f'get_video_profiles failed: {e}')
    else:
        print('FAILED: Could not connect to camera')

asyncio.run(main())
