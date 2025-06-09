from django.db import models


class SearchIndex(models.Model):
    
    search_name = models.CharField(max_length=1000)
    reporting_year = models.IntegerField()    

    class Meta:
        abstract = True
        managed = False
        

class EmployerSearchIndex(SearchIndex):
    
    instance = models.ForeignKey("payroll.Employer", on_delete=models.CASCADE)
    headcount = models.IntegerField()
    expenditure = models.DecimalField(decimal_places=2, max_digits=100)
    
    class Meta:
        abstract = False
        constraints = [
            models.UniqueConstraint(fields=['instance', 'reporting_year'], name='unique_employer_idx'),
        ]
        

class PersonSearchIndex(SearchIndex):
    
    instance = models.ForeignKey("payroll.Person", on_delete=models.CASCADE)
    
    class Meta:
        abstract = False
        constraints = [
            models.UniqueConstraint(fields=['instance', 'reporting_year'], name='unique_person_idx'),
        ]
  