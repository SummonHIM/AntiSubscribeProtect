# AnitSubscribeProtect

I believe you can roughly guess the purpose of this program just from the title and tags.

## Running

```
pip install --requirement requirements.txt
gunicorn --bind 0.0.0.0:8000 --bind [::]:8000 --workers 4 main:app
```

## Usage

### Root Endpoint

```
GET /

200: {
  "boards": [
    "Board/Site ID",
  ]
}
```

### Supported Boards/Sites

```
GET /board/<Board/Site ID>

200: Subscription content

400: {
    "error": "Error code",
    "details": [
        {
            "error": "Error code",
            "message": "Error message",
            "param": "Problematic parameter"
        }
    ],
    "help": {
        "description": "Board/Site description",
        "endpoint": "Endpoint",
        "example": "Usage example",
        "method": "GET",
        "name": "Board/Site ID",
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
