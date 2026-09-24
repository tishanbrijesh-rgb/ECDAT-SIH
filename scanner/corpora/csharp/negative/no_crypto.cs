using System;
using System.Collections.Generic;

class DataProcessor {
    private List<string> items = new List<string>();

    public void Add(string item) {
        items.Add(item);
    }

    public List<string> GetAll() {
        return new List<string>(items);
    }

    public int Count => items.Count;
}

class Program {
    static void Main() {
        var processor = new DataProcessor();
        processor.Add("hello");
        processor.Add("world");
        Console.WriteLine($"Count: {processor.Count}");
    }
}
