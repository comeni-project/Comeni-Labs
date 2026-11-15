"""What the builder records and builds from, without touching a row, a queue or a model.

The decisions a person or the agent made (`decisions`, `payloads`), the blueprint the resolver
produced and how a pipeline is projected from it (`blueprint`, `diff`, `reviews`), what a canvas
edit means (`intent`), and what a step needs to know (`brief`, `ports`). The shell (`mendel-api`)
stores them; the agent's tools read and write them (#463).
"""
