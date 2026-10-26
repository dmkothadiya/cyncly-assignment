namespace CynclyDoraMetrics;

public static class DoraMetricCalculator
{
    public static int CalculateDeploymentFrequency(
        IEnumerable<DateTime> deploymentDates,
        DateTime reportStart,
        DateTime reportEnd)
    {
        if (reportEnd < reportStart)
        {
            throw new ArgumentException("Report end cannot be earlier than report start.", nameof(reportEnd));
        }

        var uniqueDates = deploymentDates
            .Where(date => date >= reportStart && date <= reportEnd)
            .Select(date => date.Date)
            .Distinct()
            .Count();

        return uniqueDates;
    }

    public static double CalculateMedianLeadTimeHours(IEnumerable<TimeSpan> leadTimes)
    {
        var values = leadTimes
            .Where(duration => duration >= TimeSpan.Zero)
            .OrderBy(duration => duration.TotalHours)
            .ToArray();

        if (values.Length == 0)
        {
            return 0d;
        }

        var midpoint = values.Length / 2;

        if (values.Length % 2 == 0)
        {
            // Test changes
            return (values[midpoint - 1].TotalHours + values[midpoint].TotalHours) / 2d;
        }

        return values[midpoint].TotalHours;
    }

    public static double CalculateChangeFailureRate(int failedDeployments, int totalDeployments)
    {
        if (totalDeployments <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(totalDeployments), "Total deployment count must be greater than zero.");
        }

        return (double)failedDeployments / totalDeployments;
    }
}
