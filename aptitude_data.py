"""Original beginner-level practice questions.
Each tuple: (category, question, a, b, c, d, correct, explanation)."""

QUESTIONS = [
    # ---- Quantitative ----
    ("Quantitative", "What is 15% of 200?", "20", "25", "30", "35", "c",
     "15% of 200 = (15 / 100) x 200 = 30."),
    ("Quantitative", "A train travels 180 km in 3 hours. What is its average speed?", "50 km/h", "60 km/h", "55 km/h", "65 km/h", "b",
     "Speed = distance / time = 180 / 3 = 60 km/h."),
    ("Quantitative", "If 6 pens cost Rs 90, what is the cost of 10 pens?", "Rs 120", "Rs 140", "Rs 150", "Rs 160", "c",
     "One pen costs 90 / 6 = Rs 15, so 10 pens cost Rs 150."),
    ("Quantitative", "The average of 10, 20 and 30 is:", "15", "20", "25", "60", "b",
     "Average = (10 + 20 + 30) / 3 = 60 / 3 = 20."),
    ("Quantitative", "A shirt priced at Rs 800 is sold at a 25% discount. What is the selling price?", "Rs 500", "Rs 600", "Rs 650", "Rs 700", "b",
     "Discount = 25% of 800 = 200. Selling price = 800 - 200 = Rs 600."),
    # ---- Logical ----
    ("Logical", "Find the next number: 2, 4, 8, 16, ...", "24", "30", "32", "64", "c",
     "Each number is double the previous one, so the next is 16 x 2 = 32."),
    ("Logical", "All roses are flowers. Some flowers fade quickly. Which statement must be true?",
     "All roses fade quickly", "Some roses are flowers", "All flowers are roses", "No rose fades", "b",
     "Since all roses are flowers, it is certain that some (in fact all) roses are flowers."),
    ("Logical", "If CAT is coded as DBU (each letter moved one step forward), how is DOG coded?", "EPH", "EPG", "DPH", "FPH", "a",
     "D->E, O->P, G->H, so DOG becomes EPH."),
    ("Logical", "Ravi is taller than Sam. Sam is taller than Tej. Who is the shortest?", "Ravi", "Sam", "Tej", "Cannot be said", "c",
     "Ravi > Sam > Tej, so Tej is the shortest."),
    ("Logical", "Find the odd one out: Apple, Mango, Carrot, Banana", "Apple", "Mango", "Carrot", "Banana", "c",
     "Apple, mango and banana are fruits; carrot is a vegetable."),
    # ---- Verbal ----
    ("Verbal", "Choose the synonym of 'rapid':", "Slow", "Quick", "Late", "Weak", "b",
     "'Rapid' means fast, so 'quick' is the synonym."),
    ("Verbal", "Choose the antonym of 'ancient':", "Old", "Historic", "Modern", "Classic", "c",
     "'Ancient' means very old; its opposite is 'modern'."),
    ("Verbal", "Fill in the blank: She ___ to college every day.", "go", "goes", "going", "gone", "b",
     "With a singular subject (she) in the present simple tense, the verb takes -s: 'goes'."),
    ("Verbal", "Choose the correctly spelt word:", "Recieve", "Receive", "Receeve", "Receve", "b",
     "The rule 'i before e except after c' gives 'receive'."),
    ("Verbal", "Fill in the blank: He is good ___ mathematics.", "in", "on", "at", "with", "c",
     "The correct phrase is 'good at' a subject."),
]

CATEGORIES = ["Quantitative", "Logical", "Verbal"]
