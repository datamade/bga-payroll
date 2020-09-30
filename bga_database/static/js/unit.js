import { initDataYearToggle } from  'js/data_year_toggle'
import { Unit } from  'js/employer'

const slug = JSON.parse($('#unit-data').text()).slug;
const dataYear = $('#selected-year').text();

initDataYearToggle('units', slug, dataYear, Unit.update);
