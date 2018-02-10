import uuid

from django.db import models


class GovernmentalUnit(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Department(models.Model):
    governmental_unit = models.ForeignKey('GovernmentalUnit', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, null=True)

    def __str__(self):
        return self.name

class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    tenures = models.ManyToManyField('Salary', through='Tenure')

    def __str__(self):
        return '{0} {1}'.format(self.first_name, self.last_name)

class Position(models.Model):
    department = models.ForeignKey('Department', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)

    def __str__(self):
        return '{0} {1}'.format(self.department.name, self.title)

class Salary(models.Model):
    amount = models.FloatField()
    vintage = models.IntegerField()

    def __str__(self):
        return str(self.amount)

class Tenure(models.Model):
    person = models.ForeignKey('Person', on_delete=models.CASCADE, null=True)
    position = models.ForeignKey('Position', on_delete=models.CASCADE, null=True)
    salary = models.ForeignKey('Salary', on_delete=models.CASCADE, null=True)
    start_date = models.DateField(null=True)

    def __str__(self):
        return '{0} {1} {2}'.format(self.person,
                                    self.position,
                                    self.salary.vintage)
