/** Utility module with no cryptographic operations. */

function formatData(items) {
    return items.map(i => i.toUpperCase());
}

class DataStore {
    constructor() {
        this.data = [];
    }
    add(item) {
        this.data.push(item);
    }
    getAll() {
        return [...this.data];
    }
}

function calculateSum(a, b) {
    return a + b;
}

module.exports = { formatData, DataStore, calculateSum };
