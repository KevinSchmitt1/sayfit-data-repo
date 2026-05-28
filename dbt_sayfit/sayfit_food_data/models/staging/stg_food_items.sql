select
    item_name,
    cast(kcal_100g as double) as kcal_100g,
    cast(fat_100g as double) as fat_100g,
    cast(carbs_100g as double) as carbs_100g,
    cast(protein_100g as double) as protein_100g,
    source,
    cat_l1,
    cat_l2
from food_items_final