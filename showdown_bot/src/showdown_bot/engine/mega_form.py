from __future__ import annotations

from dataclasses import dataclass

from showdown_bot.engine.items import ItemMeta, _item_table, to_id
from showdown_bot.engine.species_meta import SpeciesFormMeta, species_meta_table


@dataclass(frozen=True)
class MegaForm:
    base_species_id: str
    form_species_id: str
    form_species_name: str
    stone_item_id: str


def mega_form_for(
    base_species_name: str,
    item_id: str,
    *,
    item_table: dict[str, ItemMeta] | None = None,
    species_meta: dict[str, SpeciesFormMeta] | None = None,
) -> MegaForm | None:
    items = _item_table() if item_table is None else item_table
    forms = species_meta_table() if species_meta is None else species_meta
    base_id = to_id(base_species_name)
    item = items.get(to_id(item_id))
    if item is None or not item.mega_stone:
        return None
    form_name = item.mega_stone.get(base_id)
    if form_name is None:
        return None
    form = forms.get(to_id(form_name))
    if form is None:
        return None
    base_form = forms.get(base_id)
    if base_form is not None:
        if (
            form.base_species_id != base_form.base_species_id
            and form.base_species_id != base_id
        ):
            return None
    elif form.base_species_id != base_id:
        return None
    return MegaForm(base_id, form.form_species_id, form.form_species_name, item.id)