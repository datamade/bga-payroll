from django.shortcuts import render

from data_import.forms import UploadForm


'''
In a workflow where the user uploads data on a per-reporting-agency basis,
I imagine having a view that renders the UploadForm.

The user provides the reporting agency, the standard data file, and the
source document or documents. If the reporting period is the standard period
(Jan. 1 - Dec. 31), the user provides the year; otherwise, they provide the
custom reporting period start and end dates.

When valid data is provided, one Upload object is created. A SourceFile
associated with the Upload is created for each raw source file; the raw files
themselves are also uploaded, perhaps to S3?

Then a delayed task (or a series of delayed tasks) is kicked off. Assuming the
user uploads only one agency at a time, these tasks:

- map People to existing People via name and Position, insert unmappable
People.
- map Positions to existing Positions via title and Employer, insert
unmappable Positions.
- insert "valid" Salaries, flag "invalid" Salaries for review.

All data is tied to the appropriate SourceFile/s.

All of the above work is done automatically, except where a Salary is
"invalid." (See "On validation" below.) "Invalid" salaries must be checked
and approved by the user.

Conversely, we expect there to be some variability among People and Positions.
The user has the option to combine these manually in the user interface, but it
is not required.

On validation:

Our working definition of "invalid" is disproportionately higher
or lower than in the previous year. By this definition, we can only "validate"
Salaries where we have a baseline for comparison, e.g., we cannot validate
Salaries for new or unmappable People. Of course, we may be able to extend the
definition to incorporate other data, like Position, although there are clear
limitations to comparability, i.e., the mayor of Chicago is going to make more
money than the mayor of a town with 5,000 people.
'''
