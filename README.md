# YouTube Content Extractor

A Flask web application for downloading and processing YouTube videos, extracting audio and subtitles.

## Features

- Extract audio from YouTube videos
- Generate subtitle/transcript files from videos
- RESTful API for client integration
- Web interface for task management
- Track task status (pending, processing, completed, failed)
- Download processed audio and subtitle files

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML, CSS (Bootstrap), JavaScript
- **Processing**: YouTube-DL/YT-DLP integration

## Project Structure

```
.
├── app.py                  # Main Flask application entry point
├── config.py               # Configuration settings
├── models.py               # Database models
├── task_loader.py          # Background task processor
├── youtube_content_extractor.py  # YouTube processing logic
├── utils.py                # Utility functions
├── init_db.py              # Database initialization script
├── routes/                 # Route blueprints
│   ├── api.py              # API endpoints
│   ├── main.py             # Main web routes
├── templates/              # HTML templates
├── static/                 # Static assets
└── download/               # Downloaded files storage
```

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/youtube-content-extractor.git
cd youtube-content-extractor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Initialize the database:
```bash
python init_db.py
```

4. Run the application:
```bash
python app.py
```

The application will be accessible at http://localhost:5000

## API Usage

### Create a download task

```
POST /api/tasks
Content-Type: application/json

{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

### Check task status

```
GET /api/tasks/{task_id}
```

### Get all tasks

```
GET /api/tasks
```

## Configuration

Key configuration options in `config.py`:

- `DOWNLOAD_FOLDER`: Path to store downloaded files
- `SQLALCHEMY_DATABASE_URI`: Database connection string
- `STORAGE_LIMIT`: Maximum storage limit for downloads
- `SUBTITLES_PER_PAGE`: Pagination setting for subtitle listing

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.