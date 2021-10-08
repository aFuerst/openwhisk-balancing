import math

cold = True

def main(args):
    global cold
    was_cold = cold
    cold = False
    name = args.get("name", "stranger")
    greeting = "Hello " + name + " from python!"
    return {"body": {"greeting": greeting, "cold":was_cold} }
