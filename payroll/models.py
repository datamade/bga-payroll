from django.db import models


class GovernmentalUnit(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Department(models.Model):
    governmental_unit = models.ForeignKey('GovernmentalUnit', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Person(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    tenures = models.ManyToManyField('Salary', through='Tenure')

    def __str__(self):
        return '{0} {1}'.format(self.first_name, self.last_name)

class Position(models.Model):
    department = models.ForeignKey('Department', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)

    def __str__(self):
        return '{0} {1}'.format(self.department.name, self.title)

class Salary(models.Model):
    amount = models.FloatField()
    start_date = models.DateField(null=True)
    vintage = models.IntegerField()

    def __str__(self):
        return self.amount

class Tenure(models.Model):
    person = models.ForeignKey('Person', on_delete=models.CASCADE)
    position = models.ForeignKey('Position', on_delete=models.CASCADE)
    salary = models.ForeignKey('Salary', on_delete=models.CASCADE)

    def __str__(self):
        return '{0} {1} {2}'.format(self.person,
                                    self.position,
                                    self.salary.vintage)
