package main

/** Simple utility with no cryptographic operations. */

func processItems(items []string) []string {
	result := make([]string, len(items))
	for i, item := range items {
		result[i] = item + "_processed"
	}
	return result
}

func sum(a, b int) int {
	return a + b
}

func reverse(s string) string {
	runes := []rune(s)
	for i, j := 0, len(runes)-1; i < j; i, j = i+1, j-1 {
		runes[i], runes[j] = runes[j], runes[i]
	}
	return string(runes)
}
