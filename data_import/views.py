from django.shortcuts import render

from data_import.forms import UploadForm


'''
In this workflow, I imagine having an upload view that renders the
UploadForm.

The user provides the reporting agency, the standard data file, and the
source document or documents.

When valid data is provided, one Upload object is created. A SourceFile
associated with the Upload is created for each raw source file; the raw files
themselves are also uploaded, perhaps to S3?

Then a delayed task (or a series of delayed tasks) is kicked off.

Assuming the user uploads only one agency at a time, these tasks should:

- Map People to existing People, insert unmappable People
- Map Positions to existing Positions, insert unmappable Positions
- Insert salaries

We expect People and Positions to be fairly inconsistent over time. Allow the
user to combine these in some user interface if need be, but don't force them
to.
'''
