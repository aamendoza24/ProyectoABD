import requests
import base64
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

class ImageService:
    IMGBB_API_KEY = '1a033715127541fff5dbf3fb2dd640d4'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    @classmethod
    def allowed_file(cls, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in cls.ALLOWED_EXTENSIONS

    @classmethod
    def upload_to_imgbb(cls, image_file):
        try:
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            payload = {
                'key': cls.IMGBB_API_KEY,
                'image': base64_image,
                'name': f"{uuid.uuid4()}_{secure_filename(image_file.filename)}",
            }
            
            response = requests.post('https://api.imgbb.com/1/upload', payload)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return {
                        'url': result['data']['url'],
                        'delete_url': result['data']['delete_url'],
                        'thumbnail': result['data']['thumb']['url'],
                        'medium': result['data']['medium']['url'] if 'medium' in result['data'] else result['data']['url']
                    }
            
            if current_app:
                current_app.logger.error(f"Error al subir imagen a ImgBB: {response.text}")
            return None
            
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error al subir imagen a ImgBB: {str(e)}")
            return None
