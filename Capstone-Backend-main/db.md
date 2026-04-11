Table users {
  id uuid [primary key]
  email string
  password_hash string
  role_id integer
  created_at timestamp
}

Table roles {
  id integer [primary key]
  name string
  code string
  created_at timestamp
}

Table surveys {
  id uuid [primary key]
  name string
  token string
  created_by uuid
  created_at timestamp
  start_time timestamp
  end_time timestamp
  status string // pending, active, inactive
}

Table questions {
  id uuid [primary key]
  survey_id uuid
  type string // 'mcq' or 'arrow'
  title string
  question_image string
  is_visible boolean
  order_index integer
  created_at timestamp
}

Table question_options {
  id uuid [primary key]
  question_id uuid
  image_url string
  order_index integer
}

Table question_config {
  question_id uuid [primary key]
  correct_angle float
  tolerance float
  standing_position string
  looking_direction string
}

Table participants {
  id uuid [primary key]
  survey_id uuid
  code string
  name string
  school string
  grade string
  dob timestamp
  created_at timestamp
}

Table attempts {
  id uuid [primary key]
  survey_id uuid
  participant_id uuid
  start_time timestamp
  end_time timestamp
  status string
  score float
  completion_percentage float
}

Table answers {
  id uuid [primary key]
  attempt_id uuid
  question_id uuid
  selected_option_id uuid
  user_angle float
  created_at timestamp
}

Ref: surveys.created_by > users.id
Ref: questions.survey_id > surveys.id
Ref: question_options.question_id > questions.id
Ref: question_config.question_id - questions.id
Ref: participants.survey_id > surveys.id
Ref: attempts.survey_id > surveys.id
Ref: attempts.participant_id > participants.id
Ref: answers.attempt_id > attempts.id
Ref: answers.question_id > questions.id
Ref: answers.selected_option_id > question_options.id
Ref: users.role_id > roles.id
