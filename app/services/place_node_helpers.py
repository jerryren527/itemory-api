from rest_framework import status
from rest_framework.response import Response


def get_place_node_data(node_type, id):

    # obj = get_object(node_type, id)
    # children = get_children(obj, node_type)

    # return obj, children
    node = {
        "id": 12,
        "type": "container",
        "name": "Closet Box",
        "description": "Winter stuff",
        "picture": None,

        "parent": {
            "id": 5,
            "type": "room",
            "name": "Bedroom"
        },

        "meta": {
            "level": 2
        }
    }

    children = [
        {
            "id": 45,
            "type": "container",
            "name": "Small Box",
            "preview": {
                "item_count": 3,
                "container_count": 1
            }
        },
        {
            "id": 99,
            "type": "item",
            "name": "iPhone Charger",
            "preview": {
                "quantity": 2,
                "status": "stored"
            }
        }
    ]
    res = {
        "node": node,
    }

    return Response(res, status=status.HTTP_200_OK)
