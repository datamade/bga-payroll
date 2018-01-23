# Data questions

1. In what formats do you receive payroll data?
2. What transformations do you apply to payroll data? Are they standard, or applied on a case-by-case basis? (Implied question: Is the data you receive consistent enough to have standard transformations?)
3. Are there any gotchas to working with the data that we should be aware of, i.e., strange codes or dates, salary outliers?
    - How is `date_started` generated?
    - What does a timestamp of 0 mean for `date_started`?
    - It seems like a minority of records contain a `date_started`. Is this expected moving forward?
4. Is any data inconsistent between years, i.e., name, such that John Smith is Jon Smith next year, surname changes due to marriage, etc.? Does this matter to you now, and if so, do you have any existing practices for dealing with it?
5. What does `record` in 2016 refer to?
6. What does `agency_number` (2016) and `id` (2017) refer to?
7. What do the `upload_date` / `upload_date_time` fields in 2016 indicate? Are they important?
8. Are there any transformations applied in the view that we should be aware of when sanity checking raw records against the existing database?