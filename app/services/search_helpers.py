from ..models import Room, Container, Item, Home, HomeMembership


def get_home_ids_for_user(user):
    return set(HomeMembership.objects.filter(user=user).values_list('home_id', flat=True))


def _expand_container_subtree(seed_ids, home_by_container):
    """
    BFS down Container.parent_container_id starting from seed_ids (already
    present as keys in home_by_container, mapping container_id -> (home_id,
    home_name)). Container.level is capped at 5, so this converges in at most
    5 iterations. Returns the full set of descendant ids, including the seeds.
    """
    all_ids = set(seed_ids)
    frontier = set(seed_ids)
    for _ in range(5):
        if not frontier:
            break
        next_containers = Container.objects.filter(parent_container_id__in=frontier)
        new_frontier = set()
        for c in next_containers:
            if c.id in all_ids:
                continue
            all_ids.add(c.id)
            new_frontier.add(c.id)
            home_by_container[c.id] = home_by_container[c.parent_container_id]
        frontier = new_frontier
    return all_ids


def _resolve_container_home(container):
    """Walk up the parent_container chain (bounded by max level=5) to find the owning (home_id, home_name)."""
    node = container
    for _ in range(6):
        if node.room_id:
            room = node.room
            return (room.home_id, room.home.name)
        if node.parent_container_id is None:
            return None
        node = node.parent_container
    return None


def resolve_search_scope(user, scope, origin_type, origin_id):
    """
    Returns a dict:
      {
        'match_room_ids': set[int],       # rooms eligible to appear as results
        'match_container_ids': set[int],  # containers eligible to appear as results
        'item_room_ids': set[int],        # rooms whose direct items are in scope
        'item_container_ids': set[int],   # containers whose direct items are in scope
        'home_by_room': {room_id: (home_id, home_name)},
        'home_by_container': {container_id: (home_id, home_name)},
      }
    Raises ValueError('not_found' | 'invalid_scope' | 'invalid_origin_type') if the
    scope/origin combination is invalid or not accessible to `user`.
    """
    user_home_ids = get_home_ids_for_user(user)

    if scope == 'everywhere':
        homes = {h.id: (h.id, h.name) for h in Home.objects.filter(id__in=user_home_ids)}
        rooms = list(Room.objects.filter(home_id__in=user_home_ids))
        room_ids = {r.id for r in rooms}
        home_by_room = {r.id: homes[r.home_id] for r in rooms}
        home_by_container = {}
        seed_ids = set()
        for c in Container.objects.filter(room_id__in=room_ids):
            seed_ids.add(c.id)
            home_by_container[c.id] = home_by_room[c.room_id]
        container_ids = _expand_container_subtree(seed_ids, home_by_container)
        return {
            'match_room_ids': room_ids,
            'match_container_ids': container_ids,
            'item_room_ids': room_ids,
            'item_container_ids': container_ids,
            'home_by_room': home_by_room,
            'home_by_container': home_by_container,
        }

    if scope != 'folder':
        raise ValueError('invalid_scope')

    if origin_type == 'home':
        if origin_id not in user_home_ids:
            raise ValueError('not_found')
        try:
            home = Home.objects.get(pk=origin_id)
        except Home.DoesNotExist:
            raise ValueError('not_found')
        home_tag = (home.id, home.name)
        rooms = list(Room.objects.filter(home_id=origin_id))
        room_ids = {r.id for r in rooms}
        home_by_room = {rid: home_tag for rid in room_ids}
        home_by_container = {}
        seed_ids = set()
        for c in Container.objects.filter(room_id__in=room_ids):
            seed_ids.add(c.id)
            home_by_container[c.id] = home_tag
        container_ids = _expand_container_subtree(seed_ids, home_by_container)
        return {
            'match_room_ids': room_ids,
            'match_container_ids': container_ids,
            'item_room_ids': room_ids,
            'item_container_ids': container_ids,
            'home_by_room': home_by_room,
            'home_by_container': home_by_container,
        }

    if origin_type == 'room':
        try:
            room = Room.objects.select_related('home').get(pk=origin_id)
        except Room.DoesNotExist:
            raise ValueError('not_found')
        if room.home_id not in user_home_ids:
            raise ValueError('not_found')
        home_tag = (room.home_id, room.home.name)
        home_by_container = {}
        seed_ids = set(Container.objects.filter(room_id=origin_id).values_list('id', flat=True))
        for cid in seed_ids:
            home_by_container[cid] = home_tag
        container_ids = _expand_container_subtree(seed_ids, home_by_container)
        return {
            'match_room_ids': set(),
            'match_container_ids': container_ids,
            'item_room_ids': {origin_id},
            'item_container_ids': container_ids,
            'home_by_room': {origin_id: home_tag},
            'home_by_container': home_by_container,
        }

    if origin_type == 'container':
        try:
            origin_container = Container.objects.get(pk=origin_id)
        except Container.DoesNotExist:
            raise ValueError('not_found')
        home_tag = _resolve_container_home(origin_container)
        if home_tag is None or home_tag[0] not in user_home_ids:
            raise ValueError('not_found')
        home_by_container = {origin_id: home_tag}
        seed_ids = set(Container.objects.filter(parent_container_id=origin_id).values_list('id', flat=True))
        for cid in seed_ids:
            home_by_container[cid] = home_tag
        container_ids = _expand_container_subtree(seed_ids, home_by_container)
        return {
            'match_room_ids': set(),
            'match_container_ids': container_ids,
            'item_room_ids': set(),
            'item_container_ids': container_ids | {origin_id},
            'home_by_room': {},
            'home_by_container': home_by_container,
        }

    raise ValueError('invalid_origin_type')
