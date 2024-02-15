from collections import deque


class LimitedArray:
    def __init__(self, max_length=8):
        self.max_length = max_length
        self.array = deque()

    def append(self, item):
        self.array.append(item)
        if len(self.array) > self.max_length:
            self.array.popleft()

    def __getitem__(self, index):
        return self.array[index]

    def __len__(self):
        return len(self.array)

    def __str__(self):
        return str(list(self.array))

    def __iter__(self):
        return iter(self.array)

    def get_last_item(self):
        if len(self.array) > 0:
            return self.array[-1]
        else:
            return 0
