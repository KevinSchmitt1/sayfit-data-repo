select *
from {{ ref('stg_food_items') }}
where item_name is not null
  and trim(item_name) != ''
  and kcal_100g between 0 and 1000
  and fat_100g between 0 and 100
  and carbs_100g between 0 and 100
  and protein_100g between 0 and 100