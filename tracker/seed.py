DEPOTS = [
    ("Central Depot", "Central", 3), ("North Depot", "North", 2),
    ("South Depot", "South", 2), ("East Depot", "East", 2), ("West Depot", "West", 2),
]
HANDLERS = [
    ("H-101", "Ravi Kumar", "Central Depot", "Mechanical,Tyre,Fuel,Accident,Electrical", 3),
    ("H-102", "Asha Nair", "North Depot", "Mechanical,Tyre,Accident", 2),
    ("H-103", "Imran Shah", "South Depot", "Mechanical,Fuel,Electrical", 2),
    ("H-104", "Leela Das", "East Depot", "Tyre,Electrical,Accident", 2),
    ("H-105", "Dev Patel", "West Depot", "Mechanical,Fuel,Accident", 2),
]
# Each letter is a route zone prefix. Distances are km to depots, ordered below.
DISTANCES = {
    "A": [2, 8, 12, 9, 13], "B": [4, 3, 11, 12, 9], "C": [7, 10, 3, 8, 12],
    "D": [9, 12, 8, 2, 7], "E": [11, 9, 10, 8, 3], "F": [5, 7, 8, 9, 10],
    "G": [8, 4, 9, 10, 6], "H": [10, 8, 6, 4, 2],
}
