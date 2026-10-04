"""Entry point for {{name}}."""


def greet(name: str) -> str:
    """Return a greeting for `name`."""
    name = name.strip()
    if not name:
        raise ValueError("name must not be empty")
    return f"Hello, {name}!"


def main() -> None:
    print(greet("world"))


if __name__ == "__main__":
    main()
