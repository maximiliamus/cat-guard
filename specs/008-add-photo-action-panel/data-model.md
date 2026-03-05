# data-model.md

## Entities

- Photo (in-memory)
  - timestamp: datetime
  - bytes: blob
  - source: enum('clean-capture')

## Validation rules

- `photo_image_quality` must be integer 1..100
- `photo_image_format` must be `'jpg'` (JPEG only for MVP; other formats are future work)

## Relationships

- Photo is transient and not persisted beyond save; no DB relations.
