import re

with open(r'e:\VMS\backend\services\onvif_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all asyncio.to_thread(cam.xxx) with _smart_call(cam.xxx)
content = content.replace('asyncio.to_thread(cam.', '_smart_call(cam.')

# Replace standalone 'await _smart_call(cam.create_media_service)' with the attach helper
content = content.replace(
    'await _smart_call(cam.create_media_service)',
    'await self._create_and_attach_service(cam, "media")'
)

with open(r'e:\VMS\backend\services\onvif_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Count replacements
count = content.count('_smart_call(cam.')
print(f'Total _smart_call(cam.) occurrences: {count}')

remaining = content.count('to_thread')
print(f'Remaining to_thread occurrences: {remaining}')
