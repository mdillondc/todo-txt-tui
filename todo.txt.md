# Todo.txt

Note! This list does not explain every feature of TodoTxtTUI, but it does explain the most important aspects of the todo.txt format, as well as some quality-of-life improvements unique to TodoTxtTUI.

# Task structure

```
x (A) 2024-01-20 2024-01-10 Verify harddrive health +personal @pc t:2023-01-15 due:2023-01-20 rec:+1m 
```

| Component                 | Explanation                              |
|---------------------------|------------------------------------------|
| `x`                       | Indicates that the task is complete      |
| `(A)`                     | The task has the highest priority        |
| `2024-01-20`              | The task was completed on 2024-01-20     |
| `2024-01-10`              | The task was created on 2024-01-10       |
| `Verify harddrive health` | Task text                                |
| `+personal`               | Task project                             |
| `@pc`                     | Task context                             |
| `t:2023-01-15`            | Threshold date                           |
| `due:2023-01-20`          | Task is due 2024-01-20                   |
| `rec:+1m`                 | Task will repeat on the 20th every month |
| `h:1`                     | Task is hidden                           |

## Priorities

```
(A) This task is most important
(B) This task is moderately important
(C) This task is less important
```

## Due Dates

Specify using `due:` followed by date `YYYY-MM-DD` or use natural language like `due:tomorrow`.

Example task: `Hello world due:2024-05-18`.

**NLP (Natural Language Processing)**  
Convert natural language like `due:tomorrow` into the correct yyyy-mm-dd formatted date. Logic for days of week sets due date next occurrence of day in question, even if today is that day. That means that if today is Tuesday and you write `due:tue`, the date will be set to Tuesday of next week. The same logic applies to next week/month.

* `due:tom` or `due:tomorrow`.
* `due:tue` or `due:tuesday`: Set date to the upcoming Tuesday (works for all days).
* `due:nw` or `due:nextweek`: Monday the following week.
* `due:nm` or `due:nextmonth`: 1st of next month.
* `due:10jan`: Upcoming January 10th.
* `due:10jan2027`: January 10th, 2027.

## Recurring tasks

Example task: `Hello world due:2024-05-18 rec:5d`. When completing the task, a new task will be created 5 days in the future based on the date when you completed the task

Recurrences can be specified in: `d` (days), `w` (weeks), `m` (months), `y` (years).

**Strict recurrence**  
Use the `+` symbol. When completing the task, a new task will be created 5 days after the tasks' due date regardless of the date when you complete the task. Useful for keeping track of birthday's and similar things where the recurrence date must always fall on the same date regardless of when you complete the task.

Example: `(A) Marie +birthday @home due:2023-10-30 rec:+1y`. Marie's birthday will repeat on Oct. 30th every year.

## Projects and Contexts

This is a `+project` and this is a `@context`.

Example: `Hello world +server @pc`.

## Threshold Dates

Threshold is set with `t:`. E.g. `Task t:2024-10-10`. That means the task won't become visible until `2024-10-10`.

Thresholds can be combined with recurrences and due dates.

### Strict-mode Recurrence

- **Behavior**: The recurrence interval is added to both the due and threshold dates.
- **Example**:
    - Task: `"2021-01-01 taxes are due in a month t:2021-03-30 due:2021-04-30 rec:+1y"`
    - On completion (e.g., on 2021-04-15), the task is marked complete and a new task is created:
        - Completed Task: `"x 2021-04-15 2021-01-01 taxes are due in a month t:2021-03-30 due:2021-04-30 rec:+1y"`
        - New Task: `"2021-04-15 taxes are due in a month t:2022-03-30 due:2022-04-30 rec:+1y"`

### Non-strict Mode Recurrence

- **Behavior**: 
    - Calculate the number of days between the threshold (`t`) and due (`due`) dates.
    - Increment `due` by the recurrence interval.
    - Update `t` to preserve the initial window between `t` and `due`.
- **Example**:
    - Task: `"2021-07-05 Water plants @home +quick due:2021-07-19 t:2021-07-09 rec:14d"`
    - On completion (e.g., on 2021-07-13), the task is marked complete and a new task is created:
        - Completed Task: `"x 2021-07-13 2021-07-05 Water plants @home +quick due:2021-07-19 t:2021-07-09 rec:14d"`
        - New Task: `"2021-07-13 Water plants @home +quick due:2021-07-27 t:2021-07-17 rec:14d"`

## Task normalization/reconstruction

Automatically fixes mangled tasks. 

Enter a task like this:
  * `Go +someProject to @work [YouTube](https://youtube.com) and (B) watch [these beautiful dogs!](https://www.youtube.com/watch?v=1VHRiwma05c). rec:+1d @pc +hello due:2023-01-01`

It will be reconstructed like this:

  * `(B) Go to [YouTube](https://youtube.com) and watch [these beautiful dogs!](https://www.youtube.com/watch?v=1VHRiwma05c). +hello +someProject @pc @work due:2023-01-01 rec:+1d`

And display like this:

![Reconstructed task](img/reconstructed-task.png)

## Links

Tasks can multiple links either plain or in markdown.

```
Hello [world](https://example.com)
Another task https://example.com
```

See [Keybindings](https://github.com/mdillondc/todo-txt-tui/tree/main#keybindings) for how to open links.