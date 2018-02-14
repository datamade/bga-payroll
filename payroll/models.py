import uuid

from django.db import models

class Employer(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', null=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class Person(models.Model):
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    salaries = models.ManyToManyField('Salary')

    def __str__(self):
        return '{0} {1}'.format(self.first_name, self.last_name)

class Position(models.Model):
    employer = models.ForeignKey('Employer', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)

    def __str__(self):
        return '{0} {1}'.format(self.employer.name, self.title)

class Salary(models.Model):
    position = models.ForeignKey('Position', on_delete=models.CASCADE)
    amount = models.FloatField()
    start_date = models.DateField(null=True)
    vintage = models.IntegerField()

    def __str__(self):
        return '{0} {1}'.format(self.amount, self.position)
