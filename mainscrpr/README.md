# LCWaikiki Management System

A Django-powered web application for managing and tracking LC Waikiki brand data through a comprehensive REST API.

## Key Features

- Product and brand data management
- Automated web scraping with intelligent change detection
- Multiple brand category tracking
- Historical URL tracking (new, deleted, and available products)
- Store and inventory management
- Django REST Framework API endpoints

## System Architecture

The application consists of the following key components:

1. **Data Models**:
   - `Config`: Stores brand configuration data with price, city, and stock settings
   - `Product`: Stores product information including price, availability, and images
   - `ProductSize`: Tracks available sizes for each product
   - `City` and `Store`: Manage geographic location information
   - URL tracking models: `ProductAvailableUrl`, `ProductNewUrl`, `ProductDeletedUrl`

2. **Synchronization System**:
   - Intelligent product scraper that only updates changed data
   - Scheduled jobs for different synchronization tasks
   - Batch processing with configurable limits to prevent timeouts

3. **Admin Interface**:
   - Customized with django-unfold for a modern look and feel
   - Organized into logical sections with appropriate icons
   - Inline editing for related models

## Management Commands

### sync_products

The `sync_products` command handles synchronization between product data and URLs. It supports the following options:

```
python manage.py sync_products [options]
```

Options:
- `--batch-size`: Number of products to process in each batch (default: 10)
- `--max-items`: Maximum number of items to process in a single run (default: 100)
- `--check-deleted`: Check for deleted products only
- `--check-new`: Check for new products only
- `--update-existing`: Update existing products only
- `--all`: Perform all sync operations

### Scheduled Jobs

The system uses django-apscheduler to run the following scheduled jobs:

1. **Full synchronization** (every 4 hours):
   - Processes up to 100 items per operation
   - Checks for new products, deleted products, and updates existing products

2. **New product check** (every hour):
   - Processes up to 50 items per run
   - Focuses only on adding new products

3. **Deleted product check** (every 2 hours):
   - Processes up to 75 items per run
   - Focuses only on updating deleted product status


## Access

- Admin interface: `/admin/`
- API endpoints: `/api/v1/`

## Development Guidelines

1. New features should be implemented as separate Django apps when appropriate
2. Use Django's ORM for all database operations
3. Follow PEP 8 coding standards
4. Add comprehensive docstrings to all classes and functions
5. Write tests for new functionality
