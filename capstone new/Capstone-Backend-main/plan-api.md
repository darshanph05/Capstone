# API Endpoints Plan (RESTful CRUD)

The document defines the APIs based on the current database schema.
The APIs are designed according to RESTful standards and include full CRUD (Create, Read, Update, Delete) operations for the entities in the system.

------------------------------------------------------------------------

# 0. Authentication & User Management

## Register

POST `/api/auth/register`

Payload

``` json
{
  "email": "researcher@test.com",
  "password": "123456",
  "role_code": "RESEARCHER"
}
```

Response

``` json
{
  "id": "uuid",
  "email": "researcher@test.com",
  "created_at": "timestamp"
}
```

------------------------------------------------------------------------

## Login

POST `/api/auth/login`

Payload

``` json
{
  "email": "researcher@test.com",
  "password": "123456"
}
```

Response

``` json
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

------------------------------------------------------------------------

## Get Current User

GET `/api/auth/me`

Auth: Bearer Token

Response

``` json
{
  "id": "uuid",
  "email": "researcher@test.com",
  "role": {
    "id": 1,
    "name": "Administrator",
    "code": "ADMIN"
  }
}
```

------------------------------------------------------------------------

# 1. File Upload

API for uploading question and answer images to Cloudflare R2.

POST `/upload/file`

POST `/upload/image`

Auth: Bearer Token

Form Data

    file: binary file/image

Query Params

    folder: uploads | images (optional)

Response

``` json
{
  "filename": "image.jpg",
  "key": "images/abc123...jpg",
  "url": "https://pub-xxx.r2.dev/images/abc123...jpg",
  "content_type": "image/jpeg",
  "size": 12345
}
```

------------------------------------------------------------------------

# 2. Survey Management

Auth: Bearer Token (ADMIN / RESEARCHER)

------------------------------------------------------------------------

## Get Surveys

GET `/surveys`

Auth: Bearer Token

Behavior

- Use `sub` in JWT to resolve current user.
- Return only surveys created by current user (`created_by = current_user.id`).

Response

``` json
[
  {
    "id": "uuid",
    "name": "Semester Quiz",
    "token": "uuid",
    "created_by": "user_id",
    "status": "active",
    "start_time": "timestamp",
    "end_time": "timestamp"
  }
]
```

------------------------------------------------------------------------

## Create Survey

POST `/surveys`

Payload

``` json
{
  "id": "survey_uuid_optional",
  "name": "Semester 1 Quiz",
  "start_time": "2026-03-01T00:00:00Z",
  "end_time": "2026-04-01T00:00:00Z",
  "status": "pending",
  "questions": [
    {
      "id": "question_uuid_optional",
      "type": "mcq",
      "title": "Which drawing is correct?",
      "question_image": "https://cdn.example.com/questions/q1.png",
      "is_visible": false,
      "order_index": 1,
      "options": [
        {
          "id": "option_uuid_optional",
          "image_url": "https://cdn.example.com/options/q1-opt1.png",
          "order_index": 1
        },
        {
          "image_url": "https://cdn.example.com/options/q1-opt2.png",
          "order_index": 2
        }
      ]
    },
    {
      "id": "question_uuid_optional",
      "type": "arrow",
      "title": "Point to the stop sign",
      "question_image": "https://cdn.example.com/questions/q2.png",
      "is_visible": false,
      "order_index": 2,
      "config": {
        "id": "config_uuid_optional",
        "correct_angle": 120.5,
        "tolerance": 15,
        "standing_position": "car",
        "looking_direction": "traffic_light"
      }
    }
  ]
}
```

Response

``` json
{
  "id": "uuid",
  "name": "Semester 1 Quiz",
  "token": "public_token",
  "created_by": "user_id",
  "created_at": "timestamp",
  "start_time": "2026-03-01T00:00:00Z",
  "end_time": "2026-04-01T00:00:00Z",
  "status": "pending",
  "questions": [
    {
      "id": "uuid",
      "survey_id": "uuid",
      "type": "mcq",
      "title": "Which drawing is correct?",
      "question_image": "https://cdn.example.com/questions/q1.png",
      "is_visible": false,
      "order_index": 1,
      "created_at": "timestamp",
      "options": [
        {
          "id": "uuid",
          "question_id": "uuid",
          "image_url": "https://cdn.example.com/options/q1-opt1.png",
          "order_index": 1
        }
      ],
      "config": null
    },
    {
      "id": "uuid",
      "survey_id": "uuid",
      "type": "arrow",
      "title": "Point to the stop sign",
      "question_image": "https://cdn.example.com/questions/q2.png",
      "is_visible": false,
      "order_index": 2,
      "created_at": "timestamp",
      "options": [],
      "config": {
        "question_id": "uuid",
        "correct_angle": 120.5,
        "tolerance": 15.0,
        "standing_position": "car",
        "looking_direction": "traffic_light"
      }
    }
  ]
}
```

Notes

- If `id` is provided, the record is updated; if omitted, a new record is created.
- In update mode (`survey.id` provided), questions not present in `questions` will be deleted.
- In update mode for `mcq`, options not present in that question's `options` will be deleted.
- `mcq` requires `options` and must not include `config`.
- `arrow` requires `config` and must not include `options`.
- For `config`, use `question_id` from the existing config object as `id`.

------------------------------------------------------------------------

## Get Survey Detail

GET `/surveys/{survey_id}`

Auth: Bearer Token

Behavior

- Use `sub` in JWT to resolve current user.
- Return full survey details (questions/options/config) if survey belongs to current user.

Response

``` json
{
  "id": "uuid",
  "name": "Semester 1 Quiz",
  "token": "public_token",
  "created_by": "user_id",
  "created_at": "timestamp",
  "start_time": "timestamp",
  "end_time": "timestamp",
  "status": "pending",
  "questions": [
    {
      "id": "uuid",
      "survey_id": "uuid",
      "type": "mcq",
      "title": "Which drawing is correct?",
      "question_image": "https://cdn.example.com/questions/q1.png",
      "is_visible": true,
      "order_index": 1,
      "created_at": "timestamp",
      "options": [
        {
          "id": "uuid",
          "question_id": "uuid",
          "image_url": "https://cdn.example.com/options/q1-opt1.png",
          "order_index": 1
        }
      ],
      "config": null
    }
  ]
}
```

------------------------------------------------------------------------

## Update Survey

PUT `/api/surveys/{survey_id}`

Payload

``` json
{
  "name": "Updated name",
  "status": "active"
}
```

------------------------------------------------------------------------

## Delete Survey

DELETE `/api/surveys/{survey_id}`

------------------------------------------------------------------------

# 3. Question Management

Auth: Bearer Token

------------------------------------------------------------------------

## Get Questions

GET `/api/surveys/{survey_id}/questions`

------------------------------------------------------------------------

## Create Question

POST `/api/surveys/{survey_id}/questions`

Note: `is_visible` controls whether the question appears to students.

### MCQ

``` json
{
  "type": "mcq",
  "title": "Which drawing is correct?",
  "question_image": "https://r2/q1.jpg",
  "is_visible": false,
  "order_index": 1,
  "options": [
    {
      "image_url": "https://r2/opt1.jpg",
      "order_index": 1
    },
    {
      "image_url": "https://r2/opt2.jpg",
      "order_index": 2
    }
  ]
}
```

### Arrow Question

``` json
{
  "type": "arrow",
  "title": "Point to the stop sign",
  "question_image": "https://r2/q2.jpg",
  "is_visible": false,
  "order_index": 2,
  "config": {
    "correct_angle": 120.5,
    "tolerance": 15.0,
    "standing_position": "car",
    "looking_direction": "traffic light"
  }
}
```

------------------------------------------------------------------------

## Update Question

PUT `/api/questions/{question_id}`

Payload similar to Create, including `is_visible` for show/hide toggling.

------------------------------------------------------------------------

## Delete Question

DELETE `/api/questions/{question_id}`

------------------------------------------------------------------------

# 4. Public Survey APIs

API for students taking the survey

------------------------------------------------------------------------

## Get Survey by Token

GET `/surveys/{token}/show`

Note: Don't return `correct_angle`.
Only questions with `is_visible = true` should be returned.
Survey status must be `active`.

------------------------------------------------------------------------

## Participant Submit (Start Attempt)

POST `/participants/submit`

Payload

``` json
{
  "survey_id": "uuid",
  "code": "01",
  "name": "Jiara Martins",
  "school": "Ambience Public School",
  "grade": "6",
  "dob": "2012-05-15"
}
```

Rules

- Survey must exist and be `active`.
- Participant profile is upserted by (`survey_id`, `code`).
- A new attempt is created every submit.

Response

``` json
{
  "participant": {
    "id": "uuid",
    "survey_id": "uuid",
    "code": "01",
    "name": "Jiara Martins",
    "school": "Ambience Public School",
    "grade": "6",
    "dob": "2012-05-15"
  },
  "attempt": {
    "id": "uuid",
    "survey_id": "uuid",
    "participant_id": "uuid",
    "status": "in_progress",
    "completion_percentage": 0
  }
}
```

------------------------------------------------------------------------

## Submit One Answer

POST `/participants/attempts/{attempt_id}/answers/one`

Payload (MCQ)

``` json
{
  "question_id": "uuid",
  "selected_option_id": "uuid",
  "user_angle": null
}
```

Payload (Arrow)

``` json
{
  "question_id": "uuid",
  "selected_option_id": null,
  "user_angle": 130.5
}
```

Rules

- Survey must be `active`.
- Answer submit checks survey time window (`start_time`, `end_time`).
- Only visible questions (`is_visible = true`) are accepted.

Response

``` json
{
  "attempt_id": "uuid",
  "answer_id": "uuid",
  "completion_percentage": 40.0,
  "answered_count": 2,
  "total_questions": 5,
  "status": "in_progress"
}
```

------------------------------------------------------------------------

## Done Attempt

POST `/participants/attempts/{attempt_id}/done`

Rules

- Does not check survey time expiry.
- Marks attempt as `completed` and sets `end_time`.

Response

``` json
{
  "attempt_id": "uuid",
  "completion_percentage": 100.0,
  "answered_count": 5,
  "total_questions": 5,
  "status": "completed"
}
```

------------------------------------------------------------------------

# 5. Results & Analytics

Auth: Bearer Token

------------------------------------------------------------------------

## Get Survey Results

GET `/api/surveys/{survey_id}/results`

Query

    ?page=1&limit=20&status=completed

------------------------------------------------------------------------

## Export Results

GET `/api/surveys/{survey_id}/export`

Response

    text/csv

------------------------------------------------------------------------

## Survey Analytics

GET `/api/surveys/{survey_id}/analytics`

Response

``` json
{
  "questions": [
    {
      "question_id": "uuid",
      "correct_count": 30,
      "wrong_count": 12
    }
  ]
}
```

------------------------------------------------------------------------

# Database Schema Reference

    users
    roles
    surveys
    questions
    question_options
    question_config
    participants
    attempts
    answers
