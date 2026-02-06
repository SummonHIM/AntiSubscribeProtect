# AntiSubscribeProtect

I believe you can roughly guess the purpose of this program just from the title and tags.

Please do not promote this project on any forums, blogs, video platforms, or similar websites.

## Running

```
pip install --requirement requirements.txt
gunicorn --bind 0.0.0.0:8000 --workers 4 main:app
```

### Development & Debug

```
pip install --requirement requirements.txt
python main.py
```

### Docker

```
docker pull ghcr.io/summonhim/antisubscribeprotect
docker run -p 8000:8000 ghcr.io/summonhim/antisubscribeprotect
```

## Usage

### Root Endpoint

```
GET /

200: {
    "code": 200,
    "boards": [
        "Board/Site ID",
    ]
}
```

### Supported Boards/Sites

```
GET /board/<Board/Site ID>

200: Subscription content

400-599: {
    "code": 400,
    "details": "Error message",
    "help_msg": {
        "description": "Board/Site description",
        "example": "Usage example",
        "id": "Board/Site ID",
        "query_params": {
            "parameter": {
                "available": ["Available fixed values"],
                "default": "Default value",
                "description": "Description",
                "example": "Example",
                "required": true
            }
        }
    }
}
```
