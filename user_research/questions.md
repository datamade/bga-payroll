# Data questions

1. What are the basic fields that are important to you? (Baseline: gov unit, employer, department, name, salary, start date, data vintage) Are there fields you don't currently have that you anticipate adding this year?
1. Are there any gotchas to working with the data that we should be aware of, i.e., strange codes or dates, salary outliers?
    - How is `date_started` generated?
    - What does a timestamp of 0 mean for `date_started`?
    - It seems like a minority of records contain a `date_started`. Is this expected moving forward?
2. What's "reasonable," in terms of year-over-year salary change?
2. Is any data inconsistent between years, i.e., name, such that John Smith is Jon Smith next year, surname changes due to marriage, etc.? Does this matter to you now, and if so, do you have any existing practices for dealing with it?
3. What does `record` in 2016 refer to?
4. What do `agency_number` (2016) and `id` (2017) refer to? (Assuming gov unit...)
5. What do the `upload_date` / `upload_date_time` fields in 2016 indicate? Are they important?
6. Are there any transformations applied in the view that we should be aware of when sanity checking raw records against the existing database?